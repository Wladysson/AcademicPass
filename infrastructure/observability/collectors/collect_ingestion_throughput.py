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
class CollectorConfig:
    elasticsearch_url: str
    elasticsearch_index: str
    metrics_port: int
    collection_interval: float
    request_timeout: float
    api_token: str | None
    username: str | None
    password: str | None


def load_config() -> CollectorConfig:
    return CollectorConfig(
        elasticsearch_url=os.getenv(
            "ELASTICSEARCH_URL",
            "http://elasticsearch:9200",
        ).rstrip("/"),
        elasticsearch_index=os.getenv(
            "ELASTICSEARCH_INDEX",
            "enade-questions",
        ),
        metrics_port=int(os.getenv("METRICS_PORT", "9202")),
        collection_interval=float(
            os.getenv("COLLECTION_INTERVAL", "30")
        ),
        request_timeout=float(os.getenv("REQUEST_TIMEOUT", "15")),
        api_token=os.getenv("ELASTICSEARCH_API_TOKEN"),
        username=os.getenv("ELASTICSEARCH_USERNAME"),
        password=os.getenv("ELASTICSEARCH_PASSWORD"),
    )


class IngestionThroughputCollector:
    def __init__(self, config: CollectorConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.stop_event = Event()
        self.registry = CollectorRegistry()

        self.indexed_documents = Gauge(
            "academicpass_ingestion_indexed_documents_total",
            "Current number of documents indexed in Elasticsearch",
            registry=self.registry,
        )

        self.indexed_documents_delta = Gauge(
            "academicpass_ingestion_indexed_documents_delta",
            "Documents indexed since the previous collection",
            registry=self.registry,
        )

        self.ingestion_throughput = Gauge(
            "academicpass_ingestion_throughput_documents_per_second",
            "Estimated document indexing throughput",
            registry=self.registry,
        )

        self.ingestion_duration = Gauge(
            "academicpass_ingestion_collection_duration_seconds",
            "Duration of the latest ingestion measurement interval",
            registry=self.registry,
        )

        self.last_collection_timestamp = Gauge(
            "academicpass_ingestion_last_collection_timestamp",
            "Unix timestamp of the latest successful collection",
            registry=self.registry,
        )

        self.collection_errors = Gauge(
            "academicpass_ingestion_collection_errors",
            "Number of errors in the latest collection",
            registry=self.registry,
        )

        self.previous_count: int | None = None
        self.previous_timestamp: float | None = None

        self._configure_authentication()

    def _configure_authentication(self) -> None:
        if self.config.api_token:
            self.session.headers.update(
                {
                    "Authorization": (
                        f"ApiKey {self.config.api_token}"
                    )
                }
            )
        elif self.config.username and self.config.password:
            self.session.auth = (
                self.config.username,
                self.config.password,
            )

    def _request_index_count(self) -> int:
        url = (
            f"{self.config.elasticsearch_url}/"
            f"{self.config.elasticsearch_index}/_count"
        )

        response = self.session.get(
            url,
            timeout=self.config.request_timeout,
        )

        response.raise_for_status()

        payload = response.json()
        count = payload.get("count")

        if not isinstance(count, int) or count < 0:
            raise ValueError(
                "Elasticsearch returned an invalid document count"
            )

        return count

    def collect(self) -> None:
        request_started_at = time.monotonic()

        try:
            current_count = self._request_index_count()
            current_timestamp = time.time()
            current_monotonic = time.monotonic()

            if self.previous_count is None:
                self.previous_count = current_count
                self.previous_timestamp = current_monotonic

                self.indexed_documents.set(current_count)
                self.indexed_documents_delta.set(0)
                self.ingestion_throughput.set(0)
                self.ingestion_duration.set(0)
            else:
                elapsed = (
                    current_monotonic - self.previous_timestamp
                )

                delta = current_count - self.previous_count

                if delta < 0:
                    logging.warning(
                        "Indexed document count decreased. "
                        "The index may have been recreated or documents deleted."
                    )

                    delta = 0

                throughput = (
                    delta / elapsed if elapsed > 0 else 0
                )

                self.indexed_documents.set(current_count)
                self.indexed_documents_delta.set(delta)
                self.ingestion_throughput.set(throughput)
                self.ingestion_duration.set(elapsed)

                self.previous_count = current_count
                self.previous_timestamp = current_monotonic

            self.last_collection_timestamp.set(current_timestamp)
            self.collection_errors.set(0)

            logging.info(
                "Indexed documents: %d",
                current_count,
            )

        except (
            requests.RequestException,
            ValueError,
            KeyError,
        ):
            self.collection_errors.set(1)
            logging.exception(
                "Failed to collect Elasticsearch ingestion metrics"
            )

        finally:
            request_duration = (
                time.monotonic() - request_started_at
            )

            logging.debug(
                "Collection request duration: %.4f seconds",
                request_duration,
            )

    def run(self) -> None:
        logging.info(
            "Starting ingestion throughput collector on port %d",
            self.config.metrics_port,
        )

        start_http_server(
            self.config.metrics_port,
            registry=self.registry,
        )

        while not self.stop_event.is_set():
            started_at = time.monotonic()

            self.collect()

            elapsed = time.monotonic() - started_at
            wait_time = max(
                0,
                self.config.collection_interval - elapsed,
            )

            self.stop_event.wait(wait_time)

        self.session.close()
        logging.info("Ingestion throughput collector stopped.")

    def stop(self, *_: Any) -> None:
        logging.info("Shutdown signal received.")
        self.stop_event.set()


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    config = load_config()

    if config.collection_interval <= 0:
        raise ValueError(
            "COLLECTION_INTERVAL must be greater than zero"
        )

    if config.request_timeout <= 0:
        raise ValueError(
            "REQUEST_TIMEOUT must be greater than zero"
        )

    if not config.elasticsearch_index:
        raise ValueError("ELASTICSEARCH_INDEX cannot be empty")

    if config.username and not config.password:
        raise ValueError(
            "ELASTICSEARCH_PASSWORD is required when username is set"
        )

    if config.password and not config.username:
        raise ValueError(
            "ELASTICSEARCH_USERNAME is required when password is set"
        )

    collector = IngestionThroughputCollector(config)

    signal.signal(signal.SIGINT, collector.stop)
    signal.signal(signal.SIGTERM, collector.stop)

    collector.run()


if __name__ == "__main__":
    main()
