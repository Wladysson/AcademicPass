import logging
import os
import signal
import time

import redis
from prometheus_client import Gauge, start_http_server


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger("academicpass.redis-hit-rate")


REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_USERNAME = os.getenv("REDIS_USERNAME") or None
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

REDIS_SSL = os.getenv("REDIS_SSL", "false").lower() == "true"
REDIS_SOCKET_TIMEOUT = float(
    os.getenv("REDIS_SOCKET_TIMEOUT", "5")
)

METRICS_PORT = int(
    os.getenv("REDIS_METRICS_PORT", "9204")
)

COLLECTION_INTERVAL = int(
    os.getenv("REDIS_COLLECTION_INTERVAL", "30")
)

REQUEST_TIMEOUT = float(
    os.getenv("REDIS_REQUEST_TIMEOUT", "5")
)

running = True


REDIS_KEYSPACE_HITS_TOTAL = Gauge(
    "academicpass_redis_keyspace_hits_total",
    "Total acumulado de operações de leitura atendidas pelo Redis.",
)

REDIS_KEYSPACE_MISSES_TOTAL = Gauge(
    "academicpass_redis_keyspace_misses_total",
    "Total acumulado de operações de leitura não encontradas no Redis.",
)

REDIS_HIT_RATE = Gauge(
    "academicpass_redis_hit_rate",
    "Taxa de acertos do cache Redis, entre 0 e 1.",
)

REDIS_MISS_RATE = Gauge(
    "academicpass_redis_miss_rate",
    "Taxa de falhas do cache Redis, entre 0 e 1.",
)

REDIS_HITS_PER_SECOND = Gauge(
    "academicpass_redis_hits_per_second",
    "Quantidade de acertos do cache Redis por segundo.",
)

REDIS_MISSES_PER_SECOND = Gauge(
    "academicpass_redis_misses_per_second",
    "Quantidade de falhas do cache Redis por segundo.",
)

REDIS_CACHE_EFFECTIVENESS = Gauge(
    "academicpass_redis_cache_effectiveness",
    "Percentual de leituras atendidas diretamente pelo Redis.",
)

REDIS_CACHE_AVOIDED_LOOKUPS_TOTAL = Gauge(
    "academicpass_redis_avoided_backend_lookups_total",
    "Estimativa acumulada de consultas ao backend evitadas por hits.",
)

REDIS_COLLECTION_ERRORS = Gauge(
    "academicpass_redis_collection_errors",
    "Indica se ocorreu erro na última coleta: 1 para erro e 0 para sucesso.",
)

REDIS_COLLECTION_TIMESTAMP = Gauge(
    "academicpass_redis_last_collection_timestamp",
    "Timestamp Unix da última coleta bem-sucedida.",
)

REDIS_COLLECTION_DURATION = Gauge(
    "academicpass_redis_collection_duration_seconds",
    "Duração da última coleta de métricas do Redis.",
)


def stop_collector(signum, frame):
    global running

    logger.info("Recebido sinal de encerramento: %s", signum)
    running = False


def create_redis_client() -> redis.Redis:
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        username=REDIS_USERNAME,
        password=REDIS_PASSWORD,
        ssl=REDIS_SSL,
        socket_timeout=REDIS_SOCKET_TIMEOUT,
        socket_connect_timeout=REQUEST_TIMEOUT,
        decode_responses=True,
        health_check_interval=30,
    )


def get_redis_statistics(
    client: redis.Redis,
) -> tuple[int, int]:
    info = client.info(section="stats")

    hits = int(info.get("keyspace_hits", 0))
    misses = int(info.get("keyspace_misses", 0))

    return hits, misses


def calculate_rates(
    hits: int,
    misses: int,
) -> tuple[float, float]:
    total_requests = hits + misses

    if total_requests == 0:
        return 0.0, 0.0

    hit_rate = hits / total_requests
    miss_rate = misses / total_requests

    return hit_rate, miss_rate


def collect_metrics(
    client: redis.Redis,
    previous_hits: int | None,
    previous_misses: int | None,
    previous_timestamp: float | None,
) -> tuple[int, int, float]:
    started_at = time.monotonic()

    hits, misses = get_redis_statistics(client)

    total_requests = hits + misses

    hit_rate, miss_rate = calculate_rates(
        hits,
        misses,
    )

    REDIS_KEYSPACE_HITS_TOTAL.set(hits)
    REDIS_KEYSPACE_MISSES_TOTAL.set(misses)

    REDIS_HIT_RATE.set(hit_rate)
    REDIS_MISS_RATE.set(miss_rate)
    REDIS_CACHE_EFFECTIVENESS.set(hit_rate * 100)

    REDIS_CACHE_AVOIDED_LOOKUPS_TOTAL.set(hits)

    current_timestamp = time.monotonic()

    if (
        previous_hits is not None
        and previous_misses is not None
        and previous_timestamp is not None
    ):
        elapsed = current_timestamp - previous_timestamp

        if elapsed > 0:
            hits_delta = max(hits - previous_hits, 0)
            misses_delta = max(misses - previous_misses, 0)

            REDIS_HITS_PER_SECOND.set(
                hits_delta / elapsed
            )

            REDIS_MISSES_PER_SECOND.set(
                misses_delta / elapsed
            )

            interval_total = hits_delta + misses_delta

            if interval_total > 0:
                interval_hit_rate = hits_delta / interval_total
                interval_miss_rate = misses_delta / interval_total

                REDIS_HIT_RATE.set(interval_hit_rate)
                REDIS_MISS_RATE.set(interval_miss_rate)
                REDIS_CACHE_EFFECTIVENESS.set(
                    interval_hit_rate * 100
                )
    else:
        REDIS_HITS_PER_SECOND.set(0)
        REDIS_MISSES_PER_SECOND.set(0)

    REDIS_COLLECTION_DURATION.set(
        time.monotonic() - started_at
    )

    REDIS_COLLECTION_TIMESTAMP.set(time.time())
    REDIS_COLLECTION_ERRORS.set(0)

    logger.info(
        "Redis cache: hits=%s misses=%s hit_rate=%.2f%% miss_rate=%.2f%%",
        hits,
        misses,
        hit_rate * 100,
        miss_rate * 100,
    )

    return hits, misses, current_timestamp


def main() -> None:
    signal.signal(signal.SIGINT, stop_collector)
    signal.signal(signal.SIGTERM, stop_collector)

    client = create_redis_client()

    start_http_server(METRICS_PORT)

    logger.info(
        "Coletor de eficiência do Redis iniciado na porta %s",
        METRICS_PORT,
    )

    previous_hits = None
    previous_misses = None
    previous_timestamp = None

    try:
        while running:
            started_at = time.monotonic()

            try:
                (
                    previous_hits,
                    previous_misses,
                    previous_timestamp,
                ) = collect_metrics(
                    client,
                    previous_hits,
                    previous_misses,
                    previous_timestamp,
                )

            except (redis.RedisError, OSError, ValueError):
                logger.exception(
                    "Falha ao coletar métricas do Redis"
                )
                REDIS_COLLECTION_ERRORS.set(1)

            elapsed = time.monotonic() - started_at

            sleep_time = max(
                COLLECTION_INTERVAL - elapsed,
                0,
            )

            if running:
                time.sleep(sleep_time)

    finally:
        client.close()
        logger.info("Coletor de Redis finalizado")


if __name__ == "__main__":
    main()
