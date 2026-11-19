from __future__ import annotations

import logging
import time

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    REGISTRY,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    """Representação dos principais indicadores de indexação."""

    indexed_documents: float
    failed_documents: float
    processing_time_seconds: float
    consumer_lag: float


class IndexingMetrics:
    """Centraliza as métricas Prometheus do serviço de indexação."""

    def __init__(
        self,
        registry: CollectorRegistry | None = None,
        namespace: str = "academicpass",
        subsystem: str = "indexing",
    ) -> None:
        if not namespace or not subsystem:
            raise ValueError(
                "namespace e subsystem são obrigatórios."
            )

        self.registry = registry or REGISTRY

        self.documents_indexed = Counter(
            "documents_indexed_total",
            "Quantidade total de documentos indexados com sucesso.",
            labelnames=("topic",),
            namespace=namespace,
            subsystem=subsystem,
            registry=self.registry,
        )

        self.documents_failed = Counter(
            "documents_failed_total",
            "Quantidade total de documentos que falharam na indexação.",
            labelnames=("topic", "error_type"),
            namespace=namespace,
            subsystem=subsystem,
            registry=self.registry,
        )

        self.processing_duration = Histogram(
            "processing_duration_seconds",
            "Tempo de processamento dos documentos.",
            labelnames=("operation",),
            namespace=namespace,
            subsystem=subsystem,
            registry=self.registry,
            buckets=(
                0.01,
                0.025,
                0.05,
                0.1,
                0.25,
                0.5,
                1.0,
                2.5,
                5.0,
                10.0,
                30.0,
            ),
        )

        self.consumer_lag = Gauge(
            "consumer_lag",
            "Diferença entre o último offset disponível e o "
            "offset de consumo do grupo Kafka.",
            labelnames=("topic", "partition"),
            namespace=namespace,
            subsystem=subsystem,
            registry=self.registry,
        )

        self.consumer_messages = Counter(
            "consumer_messages_total",
            "Quantidade de mensagens recebidas pelo consumidor.",
            labelnames=("topic", "result"),
            namespace=namespace,
            subsystem=subsystem,
            registry=self.registry,
        )

        self.bulk_operations = Counter(
            "bulk_operations_total",
            "Quantidade de operações de indexação em lote.",
            labelnames=("result",),
            namespace=namespace,
            subsystem=subsystem,
            registry=self.registry,
        )

        self.bulk_documents = Histogram(
            "bulk_documents_count",
            "Quantidade de documentos processados por operação bulk.",
            namespace=namespace,
            subsystem=subsystem,
            registry=self.registry,
            buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000),
        )

    def registrar_documento_indexado(
        self,
        topic: str = "enade.questions.structured",
        quantidade: int = 1,
    ) -> None:
        """Registra documentos indexados com sucesso."""

        self._validar_quantidade(quantidade)
        self.documents_indexed.labels(topic=topic).inc(quantidade)

    def registrar_erro(
        self,
        error_type: str,
        topic: str = "enade.questions.structured",
        quantidade: int = 1,
    ) -> None:
        """Registra falhas durante o processamento ou indexação."""

        self._validar_quantidade(quantidade)

        if not error_type:
            raise ValueError("error_type é obrigatório.")

        self.documents_failed.labels(
            topic=topic,
            error_type=error_type,
        ).inc(quantidade)

    def registrar_mensagem_consumida(
        self,
        topic: str,
        result: str = "success",
    ) -> None:
        """Registra o resultado do consumo de uma mensagem Kafka."""

        if not topic or not result:
            raise ValueError("topic e result são obrigatórios.")

        self.consumer_messages.labels(
            topic=topic,
            result=result,
        ).inc()

    def registrar_operacao_bulk(
        self,
        quantidade_documentos: int,
        result: str = "success",
    ) -> None:
        """Registra uma operação de indexação em lote."""

        self._validar_quantidade(quantidade_documentos)

        if not result:
            raise ValueError("result é obrigatório.")

        self.bulk_operations.labels(result=result).inc()
        self.bulk_documents.observe(quantidade_documentos)

    def registrar_lag(
        self,
        topic: str,
        partition: int,
        lag: int,
    ) -> None:
        """Atualiza o lag de uma partição Kafka."""

        if not topic:
            raise ValueError("topic é obrigatório.")

        if partition < 0:
            raise ValueError("partition não pode ser negativo.")

        if lag < 0:
            raise ValueError("lag não pode ser negativo.")

        self.consumer_lag.labels(
            topic=topic,
            partition=str(partition),
        ).set(lag)

    def remover_particao(self, topic: str, partition: int) -> None:
        """Remove a métrica de uma partição que deixou de ser atribuída."""

        self.consumer_lag.remove(topic, str(partition))

    @contextmanager
    def medir_tempo(
        self,
        operation: str,
    ) -> Iterator[None]:
        """Mede a duração de uma operação."""

        if not operation:
            raise ValueError("operation é obrigatório.")

        inicio = time.perf_counter()

        try:
            yield
        finally:
            duracao = time.perf_counter() - inicio

            self.processing_duration.labels(
                operation=operation,
            ).observe(duracao)

    def exportar(self) -> bytes:
        """Exporta as métricas no formato de exposição Prometheus."""

        return generate_latest(self.registry)

    def obter_content_type(self) -> str:
        """Retorna o Content-Type esperado pelo Prometheus."""

        return CONTENT_TYPE_LATEST

    def obter_snapshot(self) -> MetricsSnapshot:
        """Retorna uma visão resumida dos indicadores coletados."""

        indexed = self._obter_total(
            self.documents_indexed,
        )

        failed = self._obter_total(
            self.documents_failed,
        )

        duration = self._obter_total_observacoes(
            self.processing_duration,
        )

        lag = self._obter_total_gauges(
            self.consumer_lag,
        )

        return MetricsSnapshot(
            indexed_documents=indexed,
            failed_documents=failed,
            processing_time_seconds=duration,
            consumer_lag=lag,
        )

    @staticmethod
    def _obter_total(metric: Counter) -> float:
        return sum(
            sample.value
            for sample in metric.collect()[0].samples
            if sample.name.endswith("_total")
        )

    @staticmethod
    def _obter_total_observacoes(metric: Histogram) -> float:
        return sum(
            sample.value
            for sample in metric.collect()[0].samples
            if sample.name.endswith("_count")
        )

    @staticmethod
    def _obter_total_gauges(metric: Gauge) -> float:
        return sum(
            sample.value
            for sample in metric.collect()[0].samples
            if sample.name == metric._name
        )

    @staticmethod
    def _validar_quantidade(quantidade: int) -> None:
        if not isinstance(quantidade, int) or quantidade < 1:
            raise ValueError(
                "A quantidade deve ser um inteiro positivo."
            )


# Instância compartilhada pelas camadas do serviço.
metrics = IndexingMetrics()
