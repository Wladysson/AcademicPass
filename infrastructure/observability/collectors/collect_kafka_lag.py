import logging
import os
import signal
import time
from typing import Any

from kafka import KafkaAdminClient, KafkaConsumer
from kafka.errors import KafkaError, NoBrokersAvailable
from prometheus_client import Gauge, start_http_server


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger("academicpass.kafka-lag")


BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "kafka:9092",
).split(",")

METRICS_PORT = int(os.getenv("KAFKA_LAG_METRICS_PORT", "9203"))
COLLECTION_INTERVAL = int(os.getenv("KAFKA_LAG_COLLECTION_INTERVAL", "30"))
REQUEST_TIMEOUT = int(os.getenv("KAFKA_LAG_REQUEST_TIMEOUT", "15"))

SECURITY_PROTOCOL = os.getenv(
    "KAFKA_SECURITY_PROTOCOL",
    "PLAINTEXT",
)

SASL_MECHANISM = os.getenv("KAFKA_SASL_MECHANISM")
SASL_USERNAME = os.getenv("KAFKA_SASL_USERNAME")
SASL_PASSWORD = os.getenv("KAFKA_SASL_PASSWORD")

CLIENT_ID = os.getenv(
    "KAFKA_LAG_CLIENT_ID",
    "academicpass-kafka-lag-collector",
)

CONSUMER_GROUPS = [
    group.strip()
    for group in os.getenv("KAFKA_CONSUMER_GROUPS", "").split(",")
    if group.strip()
]

TOPIC_FILTER = [
    topic.strip()
    for topic in os.getenv("KAFKA_LAG_TOPICS", "").split(",")
    if topic.strip()
]

running = True


KAFKA_PARTITION_LAG = Gauge(
    "academicpass_kafka_partition_lag",
    "Número de mensagens pendentes por tópico, grupo e partição.",
    ["topic", "consumer_group", "partition"],
)

KAFKA_GROUP_LAG = Gauge(
    "academicpass_kafka_consumer_group_lag",
    "Lag total de um consumer group por tópico.",
    ["topic", "consumer_group"],
)

KAFKA_GROUP_PARTITIONS = Gauge(
    "academicpass_kafka_consumer_group_partitions",
    "Quantidade de partições atribuídas ou registradas para um grupo.",
    ["consumer_group"],
)

KAFKA_COLLECTION_ERRORS = Gauge(
    "academicpass_kafka_lag_collection_errors",
    "Indica se ocorreu erro na última coleta: 1 para erro e 0 para sucesso.",
)

KAFKA_COLLECTION_TIMESTAMP = Gauge(
    "academicpass_kafka_lag_last_collection_timestamp",
    "Timestamp Unix da última coleta bem-sucedida.",
)


def stop_collector(signum: int, frame: Any) -> None:
    global running

    logger.info("Recebido sinal de encerramento: %s", signum)
    running = False


def create_kafka_config() -> dict[str, Any]:
    config: dict[str, Any] = {
        "bootstrap_servers": BOOTSTRAP_SERVERS,
        "client_id": CLIENT_ID,
        "request_timeout_ms": REQUEST_TIMEOUT * 1000,
        "api_version_auto_timeout_ms": REQUEST_TIMEOUT * 1000,
    }

    if SECURITY_PROTOCOL != "PLAINTEXT":
        config["security_protocol"] = SECURITY_PROTOCOL

    if SASL_MECHANISM:
        config["sasl_mechanism"] = SASL_MECHANISM

    if SASL_USERNAME:
        config["sasl_plain_username"] = SASL_USERNAME

    if SASL_PASSWORD:
        config["sasl_plain_password"] = SASL_PASSWORD

    return config


def create_admin_client() -> KafkaAdminClient:
    config = create_kafka_config()

    return KafkaAdminClient(
        **config,
    )


def create_consumer(group_id: str) -> KafkaConsumer:
    config = create_kafka_config()

    return KafkaConsumer(
        group_id=group_id,
        enable_auto_commit=False,
        consumer_timeout_ms=REQUEST_TIMEOUT * 1000,
        **config,
    )


def get_consumer_groups(
    admin_client: KafkaAdminClient,
) -> list[str]:
    if CONSUMER_GROUPS:
        return CONSUMER_GROUPS

    groups = admin_client.list_consumer_groups()

    return sorted(
        group_id
        for group_id, _ in groups
    )


def get_group_offsets(
    admin_client: KafkaAdminClient,
    group_id: str,
) -> dict[Any, Any]:
    offsets = admin_client.list_consumer_group_offsets(group_id)

    return offsets or {}


def get_topic_partitions(
    consumer: KafkaConsumer,
    topic: str,
) -> list[Any]:
    partitions = consumer.partitions_for_topic(topic)

    if not partitions:
        return []

    return [
        consumer._client.cluster.partitions_for_topic(topic)
        for _ in []
    ] or [
        __import__("kafka").TopicPartition(topic, partition)
        for partition in sorted(partitions)
    ]


def collect_group_lag(
    admin_client: KafkaAdminClient,
    group_id: str,
) -> None:
    consumer = create_consumer(group_id)

    try:
        offsets = get_group_offsets(admin_client, group_id)

        if not offsets:
            logger.debug(
                "Consumer group sem offsets registrados: %s",
                group_id,
            )
            KAFKA_GROUP_PARTITIONS.labels(
                consumer_group=group_id,
            ).set(0)
            return

        group_lag_by_topic: dict[str, int] = {}
        partition_count = 0

        for topic_partition, committed_offset in offsets.items():
            topic = topic_partition.topic
            partition = topic_partition.partition

            if TOPIC_FILTER and topic not in TOPIC_FILTER:
                continue

            if committed_offset.offset < 0:
                logger.debug(
                    "Offset não inicializado: grupo=%s tópico=%s partição=%s",
                    group_id,
                    topic,
                    partition,
                )
                continue

            end_offsets = consumer.end_offsets([topic_partition])
            latest_offset = end_offsets.get(topic_partition)

            if latest_offset is None:
                continue

            lag = max(
                latest_offset - committed_offset.offset,
                0,
            )

            KAFKA_PARTITION_LAG.labels(
                topic=topic,
                consumer_group=group_id,
                partition=str(partition),
            ).set(lag)

            group_lag_by_topic[topic] = (
                group_lag_by_topic.get(topic, 0) + lag
            )

            partition_count += 1

        for topic, total_lag in group_lag_by_topic.items():
            KAFKA_GROUP_LAG.labels(
                topic=topic,
                consumer_group=group_id,
            ).set(total_lag)

        KAFKA_GROUP_PARTITIONS.labels(
            consumer_group=group_id,
        ).set(partition_count)

        logger.info(
            "Lag coletado: grupo=%s partições=%s lag_total=%s",
            group_id,
            partition_count,
            sum(group_lag_by_topic.values()),
        )

    finally:
        consumer.close()


def collect_metrics() -> None:
    admin_client = None

    try:
        admin_client = create_admin_client()
        groups = get_consumer_groups(admin_client)

        logger.info(
            "Iniciando coleta de lag para %s consumer groups",
            len(groups),
        )

        for group_id in groups:
            try:
                collect_group_lag(admin_client, group_id)

            except KafkaError:
                logger.exception(
                    "Falha ao coletar lag do consumer group: %s",
                    group_id,
                )
                KAFKA_COLLECTION_ERRORS.set(1)

        KAFKA_COLLECTION_TIMESTAMP.set(time.time())
        KAFKA_COLLECTION_ERRORS.set(0)

    except (KafkaError, NoBrokersAvailable, OSError):
        logger.exception("Falha durante a coleta de métricas do Kafka")
        KAFKA_COLLECTION_ERRORS.set(1)

    finally:
        if admin_client is not None:
            admin_client.close()


def main() -> None:
    signal.signal(signal.SIGINT, stop_collector)
    signal.signal(signal.SIGTERM, stop_collector)

    start_http_server(METRICS_PORT)

    logger.info(
        "Coletor de Kafka iniciado na porta %s",
        METRICS_PORT,
    )

    while running:
        started_at = time.monotonic()

        collect_metrics()

        elapsed = time.monotonic() - started_at
        sleep_time = max(
            COLLECTION_INTERVAL - elapsed,
            0,
        )

        if running:
            time.sleep(sleep_time)

    logger.info("Coletor de Kafka finalizado")


if __name__ == "__main__":
    main()
