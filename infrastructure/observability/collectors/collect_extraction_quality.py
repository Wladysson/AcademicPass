import logging
import os
import signal
import time
from dataclasses import dataclass
from threading import Event
from typing import Any

import requests
from prometheus_client import CollectorRegistry, Gauge, start_http_server


@dataclass(frozen=True)
class SearchConfig:
    search_url: str
    metrics_port: int
    interval_seconds: float
    timeout_seconds: float
    sample_size: int
    api_token: str | None


def load_config() -> SearchConfig:
    return SearchConfig(
        search_url=os.getenv(
            "SEARCH_URL",
            "http://search-service:8082/api/v1/questions",
        ),
        metrics_port=int(os.getenv("METRICS_PORT", "9201")),
        interval_seconds=float(os.getenv("COLLECTION_INTERVAL", "30")),
        timeout_seconds=float(os.getenv("REQUEST_TIMEOUT", "15")),
        sample_size=int(os.getenv("SAMPLE_SIZE", "20")),
        api_token=os.getenv("SEARCH_API_TOKEN"),
    )


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )


class SearchLatencyCollector:
    def __init__(self, config: SearchConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.stop_event = Event()

        self.registry = CollectorRegistry()

        self.search_latency = Gauge(
            "academicpass_search_latency_seconds",
            "Search latency percentiles by cache status",
            ["cache_status", "quantile"],
            registry=self.registry,
        )

        self.search_requests = Gauge(
            "academicpass_search_latency_samples",
            "Number of samples used to calculate search latency percentiles",
            ["cache_status"],
            registry=self.registry,
        )

        self.collection_errors = Gauge(
            "academicpass_search_latency_collection_errors",
            "Number of errors in the latest collection cycle",
            registry=self.registry,
        )

        self.last_collection_timestamp = Gauge(
            "academicpass_search_latency_last_collection_timestamp",
            "Unix timestamp of the latest collection cycle",
            registry=self.registry,
        )

        if config.api_token:
            self.session.headers.update(
                {"Authorization": f"Bearer {config.api_token}"}
            )

    def _measure_request(self, use_cache: bool) -> float:
        params = {
            "page": 0,
            "size": 10,
            "cache": str(use_cache).lower(),
        }

        started_at = time.perf_counter()

        response = self.session.get(
            self.config.search_url,
            params=params,
            timeout=self.config.timeout_seconds,
        )

        response.raise_for_status()

        return time.perf_counter() - started_at

    def _collect_samples(self, use_cache: bool) -> list[float]:
        samples: list[float] = []

        for _ in range(self.config.sample_size):
            if self.stop_event.is_set():
                break

            try:
                latency = self._measure_request(use_cache)
                samples.append(latency)
            except requests.RequestException as exc:
                logging.warning(
                    "Search request failed (cache=%s): %s",
                    use_cache,
                    exc,
                )

        return samples

    @staticmethod
    def _percentile(samples: list[float], percentile: float) -> float:
        if not samples:
            return 0.0

        ordered = sorted(samples)

        if len(ordered) == 1:
            return ordered[0]

        position = (len(ordered) - 1) * percentile
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        fraction = position - lower

        return (
            ordered[lower] * (1 - fraction)
            + ordered[upper] * fraction
        )

    def _update_metrics(
        self,
        cache_status: str,
        samples: list[float],
    ) -> None:
        self.search_requests.labels(
            cache_status=cache_status
        ).set(len(samples))

        for quantile, percentile in (
            ("p50", 0.50),
            ("p95", 0.95),
            ("p99", 0.99),
        ):
            value = self._percentile(samples, percentile)

            self.search_latency.labels(
                cache_status=cache_status,
                quantile=quantile,
            ).set(value)

    def collect(self) -> None:
        errors = 0

        for use_cache, cache_status in (
            (True, "with_cache"),
            (False, "without_cache"),
        ):
            samples = self._collect_samples(use_cache)

            if not samples:
                errors += 1
                logging.warning(
                    "No successful samples for cache status: %s",
                    cache_status,
                )

            self._update_metrics(cache_status, samples)

        self.collection_errors.set(errors)
        self.last_collection_timestamp.set(time.time())

        logging.info(
            "Search latency collection completed. Errors: %d",
            errors,
        )

    def run(self) -> None:
        logging.info(
            "Starting search latency collector on port %d",
            self.config.metrics_port,
        )

        start_http_server(
            self.config.metrics_port,
            registry=self.registry,
        )

        while not self.stop_event.is_set():
            started_at = time.monotonic()

            try:
                self.collect()
            except Exception:
                logging.exception("Unexpected collection error")
                self.collection_errors.set(1)

            elapsed = time.monotonic() - started_at
            wait_time = max(
                0,
                self.config.interval_seconds - elapsed,
            )

            self.stop_event.wait(wait_time)

        self.session.close()
        logging.info("Search latency collector stopped.")

    def stop(self, *_: Any) -> None:
        logging.info("Shutdown signal received.")
        self.stop_event.set()


def main() -> None:
    configure_logging()
    config = load_config()

    if config.interval_seconds <= 0:
        raise ValueError("COLLECTION_INTERVAL must be greater than zero")

    if config.timeout_seconds <= 0:
        raise ValueError("REQUEST_TIMEOUT must be greater than zero")

    if config.sample_size <= 0:
        raise ValueError("SAMPLE_SIZE must be greater than zero")

    collector = SearchLatencyCollector(config)

    signal.signal(signal.SIGINT, collector.stop)
    signal.signal(signal.SIGTERM, collector.stop)

    collector.run()


if __name__ == "__main__":
    main()
