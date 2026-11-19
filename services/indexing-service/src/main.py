from __future__ import annotations

import logging
import os
import signal
import threading

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse

from elasticsearch import Elasticsearch

from indexing.consumers.question_structured_consumer import (
    ConsumedQuestionEvent,
    QuestionStructuredConsumer,
)

from indexing.transformers.question_document_mapper import (
    QuestionDocumentMapper,
)

from indexing.elasticsearch.bulk_indexer import BulkIndexer

from indexing.elasticsearch.index_manager import IndexManager

from indexing.resilience.retry_policy import (
    NonRetryableError,
    RetryExhaustedError,
    RetryPolicy,
)

from indexing.resilience.dead_letter import (
    DeadLetterHandler,
)

from indexing.observability.metrics import metrics


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format=(
        "%(asctime)s %(levelname)s "
        "%(name)s - %(message)s"
    ),
)

logger = logging.getLogger("indexing.main")


SERVICE_NAME = "academicpass-indexing-service"
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")

KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:9092",
)

KAFKA_GROUP_ID = os.getenv(
    "KAFKA_GROUP_ID",
    "academicpass-indexing-group",
)

KAFKA_INPUT_TOPIC = os.getenv(
    "KAFKA_INPUT_TOPIC",
    "enade.questions.structured",
)

KAFKA_DLQ_TOPIC = os.getenv(
    "KAFKA_DLQ_TOPIC",
    "enade.indexing.dlq",
)

KAFKA_SECURITY_PROTOCOL = os.getenv(
    "KAFKA_SECURITY_PROTOCOL",
    "",
)

KAFKA_SASL_MECHANISM = os.getenv(
    "KAFKA_SASL_MECHANISM",
    "",
)

KAFKA_KERBEROS_SERVICE_NAME = os.getenv(
    "KAFKA_KERBEROS_SERVICE_NAME",
    "",
)

KAFKA_KERBEROS_PRINCIPAL = os.getenv(
    "KAFKA_KERBEROS_PRINCIPAL",
    "",
)

KAFKA_KERBEROS_KEYTAB = os.getenv(
    "KAFKA_KERBEROS_KEYTAB",
    "",
)

ELASTICSEARCH_URL = os.getenv(
    "ELASTICSEARCH_URL",
    "http://localhost:9200",
)

ELASTICSEARCH_USERNAME = os.getenv(
    "ELASTICSEARCH_USERNAME",
    "",
)

ELASTICSEARCH_PASSWORD = os.getenv(
    "ELASTICSEARCH_PASSWORD",
    "",
)

ELASTICSEARCH_INDEX = os.getenv(
    "ELASTICSEARCH_INDEX",
    "academicpass-questions",
)

CONSUMER_POLL_TIMEOUT = float(
    os.getenv("CONSUMER_POLL_TIMEOUT", "1.0")
)

MAX_RETRY_ATTEMPTS = int(
    os.getenv("MAX_RETRY_ATTEMPTS", "3")
)

DLQ_PUBLICATION_TIMEOUT = float(
    os.getenv("DLQ_PUBLICATION_TIMEOUT", "10.0")
)


class IndexingApplication:
    """Coordena os componentes e o ciclo de vida da indexação."""

    def __init__(self) -> None:
        self._consumer: QuestionStructuredConsumer | None = None
        self._elasticsearch: Elasticsearch | None = None
        self._bulk_indexer: BulkIndexer | None = None
        self._index_manager: IndexManager | None = None
        self._dead_letter: DeadLetterHandler | None = None

        self._mapper = QuestionDocumentMapper()
        self._retry_policy = RetryPolicy.for_elasticsearch(
            max_attempts=MAX_RETRY_ATTEMPTS,
        )

        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._started = False
        self._healthy = False

    @property
    def healthy(self) -> bool:
        return self._healthy

    def iniciar(self) -> None:
        """Inicializa conexões e inicia o consumidor Kafka."""

        if self._started:
            return

        logger.info("Inicializando %s.", SERVICE_NAME)

        self._inicializar_elasticsearch()
        self._inicializar_index_manager()
        self._inicializar_indexacao()
        self._inicializar_dlq()
        self._inicializar_consumidor()

        self._stop_event.clear()

        self._worker_thread = threading.Thread(
            target=self._executar_consumidor,
            name="indexing-kafka-consumer",
            daemon=True,
        )

        self._worker_thread.start()

        self._started = True
        self._healthy = True

        logger.info(
            "Serviço de indexação inicializado. "
            "Tópico de entrada: %s",
            KAFKA_INPUT_TOPIC,
        )

    def _inicializar_elasticsearch(self) -> None:
        """Estabelece a conexão com o Elasticsearch."""

        config: dict[str, Any] = {
            "hosts": [ELASTICSEARCH_URL],
            "request_timeout": 10,
            "max_retries": 3,
            "retry_on_timeout": True,
        }

        if ELASTICSEARCH_USERNAME and ELASTICSEARCH_PASSWORD:
            config["basic_auth"] = (
                ELASTICSEARCH_USERNAME,
                ELASTICSEARCH_PASSWORD,
            )

        self._elasticsearch = Elasticsearch(**config)

        self._retry_policy.execute(
            self._elasticsearch.info,
            operation_name="elasticsearch_connection",
        )

        logger.info("Conexão com Elasticsearch estabelecida.")

    def _inicializar_index_manager(self) -> None:
        """Garante que o índice de questões esteja disponível."""

        if self._elasticsearch is None:
            raise RuntimeError(
                "Cliente Elasticsearch não inicializado."
            )

        self._index_manager = IndexManager(
            client=self._elasticsearch,
            index_name=ELASTICSEARCH_INDEX,
        )

        self._retry_policy.execute(
            self._index_manager.garantir_indice,
            operation_name="ensure_elasticsearch_index",
        )

        logger.info(
            "Índice Elasticsearch '%s' verificado.",
            ELASTICSEARCH_INDEX,
        )

    def _inicializar_indexacao(self) -> None:
        """Inicializa o componente responsável pela indexação."""

        if self._elasticsearch is None:
            raise RuntimeError(
                "Cliente Elasticsearch não inicializado."
            )

        self._bulk_indexer = BulkIndexer(
            client=self._elasticsearch,
            index_name=ELASTICSEARCH_INDEX,
        )

    def _inicializar_dlq(self) -> None:
        """Inicializa o produtor responsável pela DLQ."""

        self._dead_letter = DeadLetterHandler(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            topic=KAFKA_DLQ_TOPIC,
            service_name=SERVICE_NAME,
            security_protocol=KAFKA_SECURITY_PROTOCOL or None,
            sasl_mechanism=KAFKA_SASL_MECHANISM or None,
            sasl_kerberos_service_name=(
                KAFKA_KERBEROS_SERVICE_NAME or None
            ),
            sasl_kerberos_principal=(
                KAFKA_KERBEROS_PRINCIPAL or None
            ),
            sasl_kerberos_keytab=(
                KAFKA_KERBEROS_KEYTAB or None
            ),
            publication_timeout_seconds=DLQ_PUBLICATION_TIMEOUT,
        )

    def _inicializar_consumidor(self) -> None:
        """Configura o consumidor do tópico de questões estruturadas."""

        self._consumer = QuestionStructuredConsumer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=KAFKA_GROUP_ID,
            topic=KAFKA_INPUT_TOPIC,
            security_protocol=KAFKA_SECURITY_PROTOCOL or None,
            sasl_mechanism=KAFKA_SASL_MECHANISM or None,
            sasl_kerberos_service_name=(
                KAFKA_KERBEROS_SERVICE_NAME or None
            ),
            sasl_kerberos_principal=(
                KAFKA_KERBEROS_PRINCIPAL or None
            ),
            sasl_kerberos_keytab=(
                KAFKA_KERBEROS_KEYTAB or None
            ),
            poll_timeout=CONSUMER_POLL_TIMEOUT,
        )

        self._consumer.registrar_handler(
            self._processar_evento
        )

    def _processar_evento(
        self,
        event: ConsumedQuestionEvent,
    ) -> None:
        """Transforma e indexa uma mensagem recebida do Kafka."""

        if self._bulk_indexer is None:
            raise RuntimeError(
                "Indexador Elasticsearch não inicializado."
            )

        if self._dead_letter is None:
            raise RuntimeError(
                "Produtor da DLQ não inicializado."
            )

        original_event = event.payload

        event_id = str(original_event.get("event_id", "unknown"))

        try:
            with metrics.medir_tempo("question_indexing"):
                document = self._mapper.mapear(original_event)

                resultado = self._retry_policy.execute(
                    lambda: self._bulk_indexer.indexar(document),
                    operation_name="index_question",
                )

                if not resultado.success:
                    raise RuntimeError(
                        "O Elasticsearch não confirmou a indexação "
                        f"do evento {event_id}."
                    )

            metrics.registrar_documento_indexado(
                topic=KAFKA_INPUT_TOPIC,
            )

            logger.info(
                "Questão indexada com sucesso. Evento: %s",
                event_id,
            )

        except Exception as error:
            metrics.registrar_erro(
                error_type=type(error).__name__,
                topic=KAFKA_INPUT_TOPIC,
            )

            logger.exception(
                "Falha ao processar o evento %s.",
                event_id,
            )

            try:
                self._dead_letter.encaminhar_falha(
                    original_event=original_event,
                    error=error,
                    original_topic=KAFKA_INPUT_TOPIC,
                    original_key=event.question_id,
                    metadata={
                        "consumer_group": KAFKA_GROUP_ID,
                        "service": SERVICE_NAME,
                    },
                )

            except Exception as dlq_error:
                logger.exception(
                    "Não foi possível encaminhar o evento %s "
                    "para a DLQ.",
                    event_id,
                )

                raise RuntimeError(
                    f"Falha na indexação e no encaminhamento "
                    f"para DLQ do evento {event_id}."
                ) from dlq_error

            # A mensagem foi encaminhada para a DLQ.
            # O consumidor poderá confirmar o offset original.
            return

    def _executar_consumidor(self) -> None:
        """Executa o loop de consumo em uma thread dedicada."""

        if self._consumer is None:
            logger.error("Consumidor Kafka não inicializado.")
            self._healthy = False
            return

        try:
            self._consumer.consumir()

        except Exception:
            if not self._stop_event.is_set():
                logger.exception(
                    "O loop de consumo Kafka foi interrompido."
                )
                self._healthy = False

    def parar(self) -> None:
        """Encerra os componentes de forma controlada."""

        if not self._started:
            return

        logger.info("Iniciando encerramento do indexing-service.")

        self._healthy = False
        self._stop_event.set()

        if self._consumer is not None:
            try:
                self._consumer.parar()
            except Exception:
                logger.exception(
                    "Falha ao solicitar encerramento do consumidor."
                )

        if self._worker_thread is not None:
            self._worker_thread.join(timeout=15)

            if self._worker_thread.is_alive():
                logger.error(
                    "A thread do consumidor não encerrou no prazo."
                )

        if self._dead_letter is not None:
            try:
                self._dead_letter.fechar()
            except Exception:
                logger.exception(
                    "Falha ao encerrar o produtor da DLQ."
                )

        if self._consumer is not None:
            try:
                self._consumer.fechar()
            except Exception:
                logger.exception(
                    "Falha ao fechar o consumidor Kafka."
                )

        if self._elasticsearch is not None:
            try:
                self._elasticsearch.close()
            except Exception:
                logger.exception(
                    "Falha ao fechar a conexão Elasticsearch."
                )

        self._started = False

        logger.info("Indexing-service encerrado.")


application = IndexingApplication()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia a inicialização e o encerramento da aplicação."""

    application.iniciar()

    try:
        yield
    finally:
        application.parar()


app = FastAPI(
    title="AcademicPass Indexing Service",
    description=(
        "Serviço responsável pelo consumo de questões estruturadas "
        "e indexação no Elasticsearch."
    ),
    version=SERVICE_VERSION,
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
def health_check() -> JSONResponse:
    """Retorna o estado operacional do serviço."""

    if not application.healthy:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": SERVICE_NAME,
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
        },
    )


@app.get("/ready", tags=["Health"])
def readiness_check() -> JSONResponse:
    """Verifica se a aplicação está pronta para operar."""

    if not application.healthy:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": SERVICE_NAME,
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "ready",
            "service": SERVICE_NAME,
        },
    )


@app.get("/metrics", tags=["Observability"])
def prometheus_metrics() -> Response:
    """Disponibiliza as métricas para coleta pelo Prometheus."""

    return Response(
        content=metrics.exportar(),
        media_type=metrics.obter_content_type(),
    )


def _registrar_sinais() -> None:
    """Registra sinais de encerramento do processo."""

    def handler(signum: int, frame: Any) -> None:
        logger.info(
            "Sinal %s recebido. Encerrando aplicação.",
            signum,
        )
        application.parar()

    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)


if __name__ == "__main__":
    import uvicorn

    _registrar_sinais()

    uvicorn.run(
        "indexing.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8084")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
