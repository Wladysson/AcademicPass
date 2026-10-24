from __future__ import annotations

import logging
import time

from contextlib import contextmanager
from typing import Iterator

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)


logger = logging.getLogger(__name__)


class IngestionMetrics:

    DOCUMENT_TYPES = (
        "exam",
        "answer_key",
        "guideline",
    )

    FAILURE_REASONS = (
        "timeout",
        "network",
        "validation",
        "storage",
        "unknown",
    )

    def __init__(
        self,
        registry: CollectorRegistry | None = None,
    ) -> None:
        self._registry = registry or CollectorRegistry()

        self._downloads_total = Counter(
            "ingestion_downloads_total",
            "Quantidade de downloads concluídos com sucesso.",
            labelnames=("document_type",),
            registry=self._registry,
        )

        self._download_failures_total = Counter(
            "ingestion_download_failures_total",
            "Quantidade de falhas durante downloads.",
            labelnames=("document_type", "reason"),
            registry=self._registry,
        )

        self._download_duration_seconds = Histogram(
            "ingestion_download_duration_seconds",
            "Duração dos downloads de documentos em segundos.",
            labelnames=("document_type",),
            buckets=(
                0.1,
                0.5,
                1.0,
                2.5,
                5.0,
                10.0,
                20.0,
                30.0,
                60.0,
                120.0,
                300.0,
            ),
            registry=self._registry,
        )

        self._processed_bytes_total = Counter(
            "ingestion_processed_bytes_total",
            "Quantidade acumulada de bytes processados.",
            labelnames=("document_type",),
            registry=self._registry,
        )

        self._documents_processed_total = Counter(
            "ingestion_documents_processed_total",
            "Quantidade acumulada de documentos processados com sucesso.",
            labelnames=("document_type",),
            registry=self._registry,
        )

    def registrar_download_concluido(
        self,
        document_type: str,
        duration_seconds: float,
        size_bytes: int,
    ) -> None:

        normalized_type = self._validar_tipo_documento(document_type)

        if duration_seconds < 0:
            raise ValueError("A duração do download não pode ser negativa.")

        if size_bytes <= 0:
            raise ValueError("O tamanho do documento deve ser positivo.")

        self._downloads_total.labels(
            document_type=normalized_type
        ).inc()

        self._download_duration_seconds.labels(
            document_type=normalized_type
        ).observe(duration_seconds)

        self._processed_bytes_total.labels(
            document_type=normalized_type
        ).inc(size_bytes)

        logger.debug(
            "Métricas de download registradas. document_type=%s size_bytes=%s",
            normalized_type,
            size_bytes,
        )

    def registrar_falha_download(
        self,
        document_type: str,
        reason: str = "unknown",
        duration_seconds: float | None = None,
    ) -> None:

        normalized_type = self._validar_tipo_documento(document_type)
        normalized_reason = self._validar_motivo_falha(reason)

        self._download_failures_total.labels(
            document_type=normalized_type,
            reason=normalized_reason,
        ).inc()

        if duration_seconds is not None:
            if duration_seconds < 0:
                raise ValueError("A duração não pode ser negativa.")

            self._download_duration_seconds.labels(
                document_type=normalized_type
            ).observe(duration_seconds)

    def registrar_documento_processado(
        self,
        document_type: str,
        size_bytes: int,
    ) -> None:

        normalized_type = self._validar_tipo_documento(document_type)

        if size_bytes <= 0:
            raise ValueError("O tamanho do documento deve ser positivo.")

        self._documents_processed_total.labels(
            document_type=normalized_type
        ).inc()

        self._processed_bytes_total.labels(
            document_type=normalized_type
        ).inc(size_bytes)

    @contextmanager
    def medir_download(
        self,
        document_type: str,
    ) -> Iterator[None]:

        normalized_type = self._validar_tipo_documento(document_type)
        started_at = time.perf_counter()

        try:
            yield
        except Exception:
            duration = time.perf_counter() - started_at

            self.registrar_falha_download(
                document_type=normalized_type,
                duration_seconds=duration,
            )

            raise
        else:
            duration = time.perf_counter() - started_at

            self._download_duration_seconds.labels(
                document_type=normalized_type
            ).observe(duration)

    def obter_metricas(self) -> bytes:

        return generate_latest(self._registry)

    @property
    def content_type(self) -> str:

        return CONTENT_TYPE_LATEST

    @staticmethod
    def _validar_tipo_documento(document_type: str) -> str:
        if not isinstance(document_type, str):
            raise TypeError("O tipo de documento deve ser uma string.")

        normalized_type = document_type.strip().lower()

        if normalized_type not in IngestionMetrics.DOCUMENT_TYPES:
            raise ValueError(
                f"Tipo de documento não suportado: {document_type}."
            )

        return normalized_type

    @staticmethod
    def _validar_motivo_falha(reason: str) -> str:
        if not isinstance(reason, str):
            raise TypeError("O motivo da falha deve ser uma string.")

        normalized_reason = reason.strip().lower()

        if normalized_reason not in IngestionMetrics.FAILURE_REASONS:
            return "unknown"

        return normalized_reason
