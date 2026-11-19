from __future__ import annotations

import logging
import os
import signal
import threading
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid5, NAMESPACE_URL

from fastapi import FastAPI, Response, status

from extraction.consumers.pdf_discovered_consumer import (
    PdfDiscoveredConsumer,
)
from extraction.storage.pdf_reader import PdfReader
from extraction.storage.minio_pdf_reader import MinioPdfReader
from extraction.storage.local_volume_pdf_reader import LocalVolumePdfReader
from extraction.parsers.pdf_parser import PdfParser
from extraction.parsers.question_segmenter import QuestionSegmenter
from extraction.parsers.question_classifier import QuestionClassifier
from extraction.parsers.metadata_extractor import MetadataExtractor
from extraction.media.formula_converter import FormulaConverter
from extraction.media.table_converter import TableConverter
from extraction.producers.question_structured_producer import (
    QuestionStructuredProducer,
)
from extraction.producers.extraction_error_producer import (
    ExtractionErrorProducer,
)
from extraction.resilience.dead_letter import DeadLetterHandler
from extraction.resilience.idempotency import IdempotencyManager
from extraction.schemas.question_event import (
    AnswerStatus,
    ExamComponent,
    QuestionAlternative,
    QuestionContent,
    QuestionEvent,
    QuestionMetadata,
    QuestionType,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger("extraction.main")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"A variável {name} deve ser um número inteiro.") from error


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(f"A variável obrigatória {name} não foi configurada.")

    return value


class ExtractionApplication:
    def __init__(self) -> None:
        self._consumer: PdfDiscoveredConsumer | None = None
        self._structured_producer: QuestionStructuredProducer | None = None
        self._error_producer: ExtractionErrorProducer | None = None
        self._dead_letter: DeadLetterHandler | None = None

        self._consumer_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()
        self._started = False
        self._last_error: str | None = None

        self._pdf_reader: PdfReader | None = None
        self._pdf_parser = PdfParser()
        self._question_segmenter = QuestionSegmenter()
        self._question_classifier = QuestionClassifier()
        self._metadata_extractor = MetadataExtractor()
        self._formula_converter = FormulaConverter()
        self._table_converter = TableConverter()
        self._idempotency_manager = IdempotencyManager()

    def start(self) -> None:
        if self._started:
            return

        self._configure_storage()
        self._configure_kafka()

        self._consumer.registrar_handler(self.process_discovered_pdf)

        self._consumer_thread = threading.Thread(
            target=self._consume_messages,
            name="extraction-kafka-consumer",
            daemon=True,
        )

        self._consumer_thread.start()
        self._started = True

        logger.info("Extraction service iniciado.")

    def stop(self) -> None:
        if not self._started:
            return

        logger.info("Encerrando extraction service.")

        self._shutdown_event.set()

        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=30)

        self._close_component(self._consumer)
        self._close_component(self._structured_producer)
        self._close_component(self._error_producer)

        self._started = False
        logger.info("Extraction service encerrado.")

    def _configure_storage(self) -> None:
        storage_backend = os.getenv("PDF_STORAGE_BACKEND", "minio").lower()

        if storage_backend == "minio":
            self._pdf_reader = MinioPdfReader(
                endpoint=_required_env("MINIO_ENDPOINT"),
                access_key=_required_env("MINIO_ACCESS_KEY"),
                secret_key=_required_env("MINIO_SECRET_KEY"),
                bucket_name=_required_env("MINIO_BUCKET_NAME"),
                secure=_env_bool("MINIO_SECURE", False),
                region=os.getenv("MINIO_REGION") or None,
                max_file_size_mb=_env_int("PDF_MAX_FILE_SIZE_MB", 50),
            )
        elif storage_backend == "local":
            self._pdf_reader = LocalVolumePdfReader(
                storage_path=_required_env("PDF_STORAGE_PATH"),
                max_file_size_mb=_env_int("PDF_MAX_FILE_SIZE_MB", 50),
            )
        else:
            raise RuntimeError(
                "PDF_STORAGE_BACKEND deve ser 'minio' ou 'local'."
            )

        logger.info("Armazenamento de PDFs configurado: %s", storage_backend)

    def _configure_kafka(self) -> None:
        bootstrap_servers = _required_env("KAFKA_BOOTSTRAP_SERVERS")
        group_id = os.getenv("KAFKA_CONSUMER_GROUP", "extraction-service")
        input_topic = os.getenv(
            "KAFKA_INPUT_TOPIC",
            "enade.pdfs.discovered",
        )

        security_protocol = os.getenv("KAFKA_SECURITY_PROTOCOL")
        sasl_mechanism = os.getenv("KAFKA_SASL_MECHANISM")
        sasl_username = os.getenv("KAFKA_SASL_USERNAME")
        sasl_password = os.getenv("KAFKA_SASL_PASSWORD")

        kafka_config: dict[str, Any] = {}

        if security_protocol:
            kafka_config["security.protocol"] = security_protocol

        if sasl_mechanism:
            kafka_config["sasl.mechanism"] = sasl_mechanism

        if sasl_username:
            kafka_config["sasl.username"] = sasl_username

        if sasl_password:
            kafka_config["sasl.password"] = sasl_password

        self._consumer = PdfDiscoveredConsumer(
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            topic=input_topic,
            enable_auto_commit=False,
            security_config=kafka_config,
        )

        self._structured_producer = QuestionStructuredProducer(
            bootstrap_servers=bootstrap_servers,
            security_config=kafka_config,
        )

        self._error_producer = ExtractionErrorProducer(
            bootstrap_servers=bootstrap_servers,
            security_config=kafka_config,
        )

        self._dead_letter = DeadLetterHandler(
            error_producer=self._error_producer,
        )

        logger.info(
            "Kafka configurado. Tópico de entrada: %s",
            input_topic,
        )

    def _consume_messages(self) -> None:
        try:
            self._consumer.consumir()
        except Exception as error:
            if not self._shutdown_event.is_set():
                self._last_error = str(error)
                logger.exception("Falha no consumidor Kafka.")

    def process_discovered_pdf(self, event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            raise ValueError("O evento recebido deve ser um objeto JSON.")

        event_id = str(event.get("event_id", "")).strip()
        storage_key = str(event.get("storage_key", "")).strip()
        checksum = str(event.get("checksum", "")).strip().lower()
        metadata = event.get("metadata") or {}

        if not event_id or not storage_key or not checksum:
            raise ValueError(
                "Evento inválido: event_id, storage_key e checksum são obrigatórios."
            )

        if not isinstance(metadata, dict):
            raise ValueError("O campo metadata deve ser um objeto.")

        logger.info(
            "Processando documento recebido. event_id=%s storage_key=%s",
            event_id,
            storage_key,
        )

        document = self._pdf_reader.recuperar(
            storage_key=storage_key,
            checksum=checksum,
        )

        parsed_pdf = self._pdf_parser.parse(document)

        segmented = self._question_segmenter.segment(parsed_pdf)
        classified = self._question_classifier.classify(segmented)

        extracted_metadata = self._metadata_extractor.extract(
            parsed_pdf=parsed_pdf,
            source_metadata=metadata,
            segmented_questions=segmented,
        )

        classifications = self._classification_map(classified)

        for item in segmented.questions:
            classification = classifications.get(item.number)

            if classification is None:
                logger.warning(
                    "Classificação ausente para a questão %s.",
                    item.number,
                )
                continue

            question_event = self._build_question_event(
                item=item,
                classification=classification,
                extracted_metadata=extracted_metadata,
                document_checksum=checksum,
                storage_key=storage_key,
            )

            self._structured_producer.publicar(
                question_event.to_kafka_payload()
            )

        self._structured_producer.aguardar_publicacao()

        logger.info(
            "Documento processado. event_id=%s questões=%s",
            event_id,
            len(segmented.questions),
        )

    def _classification_map(self, result: Any) -> dict[int, Any]:
        classifications: dict[int, Any] = {}

        for item in result.questions:
            classification = item.classification
            question_number = getattr(
                classification,
                "question_number",
                getattr(item.segment, "number", None),
            )

            if question_number is not None:
                classifications[int(question_number)] = classification

        return classifications

    def _build_question_event(
        self,
        item: Any,
        classification: Any,
        extracted_metadata: Any,
        document_checksum: str,
        storage_key: str,
    ) -> QuestionEvent:
        question_number = int(item.number)

        start_page = int(item.start_page)
        end_page = int(item.end_page)

        question_id = str(
            uuid5(
                NAMESPACE_URL,
                (
                    f"{document_checksum}:"
                    f"{start_page}:"
                    f"{question_number}"
                ),
            )
        )

        question_type = self._normalize_question_type(
            classification.question_type
        )

        answer_status = self._normalize_answer_status(
            classification.answer_status
        )

        alternatives = [
            QuestionAlternative(
                label=alternative.label,
                text=alternative.text,
            )
            for alternative in item.alternatives
        ]

        correct_answer = getattr(item, "correct_answer", None)

        if answer_status == AnswerStatus.ANNULLED:
            correct_answer = None

        if correct_answer:
            correct_answer = str(correct_answer).strip().upper()

        question_metadata = self._build_metadata(
            extracted_metadata,
            question_number,
        )

        question_content = QuestionContent(
            question_id=question_id,
            question_number=question_number,
            question_type=question_type,
            statement=item.statement,
            base_text=getattr(item, "base_text", None),
            alternatives=alternatives,
            correct_answer=correct_answer,
            answer_status=answer_status,
            start_page=start_page,
            end_page=end_page,
            metadata=question_metadata,
        )

        return QuestionEvent(
            question_id=question_id,
            document_checksum=document_checksum,
            storage_key=storage_key,
            question=question_content,
        )

    def _build_metadata(
        self,
        extracted_metadata: Any,
        question_number: int,
    ) -> QuestionMetadata:
        source = getattr(extracted_metadata, "document_metadata", extracted_metadata)

        def get_value(name: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(name, default)

            return getattr(source, name, default)

        area = get_value("area")
        course_code = get_value("course_code")
        course_name = get_value("course_name")
        edition_year = get_value("edition_year")
        document_type = get_value("document_type")
        source_id = get_value("source_id")
        source_name = get_value("source_name")

        component = get_value("exam_component", ExamComponent.UNKNOWN)

        return QuestionMetadata(
            area=self._field_value(area),
            course_code=self._field_value(course_code),
            course_name=self._field_value(course_name),
            edition_year=self._field_value(edition_year),
            document_type=self._field_value(document_type),
            source_id=self._field_value(source_id),
            source_name=self._field_value(source_name),
            exam_component=self._normalize_exam_component(component),
        )

    @staticmethod
    def _field_value(value: Any) -> Any:
        if hasattr(value, "value"):
            return value.value

        if hasattr(value, "confidence") and hasattr(value, "value"):
            return value.value

        return value

    @staticmethod
    def _normalize_question_type(value: Any) -> QuestionType:
        normalized = str(getattr(value, "value", value)).lower()

        aliases = {
            "objective": QuestionType.OBJECTIVE,
            "discursive": QuestionType.DISCURSIVE,
            "unknown": QuestionType.UNKNOWN,
        }

        return aliases.get(normalized, QuestionType.UNKNOWN)

    @staticmethod
    def _normalize_answer_status(value: Any) -> AnswerStatus:
        normalized = str(getattr(value, "value", value)).lower()

        aliases = {
            "correct": AnswerStatus.CORRECT,
            "annulled": AnswerStatus.ANNULLED,
            "unavailable": AnswerStatus.UNAVAILABLE,
        }

        return aliases.get(normalized, AnswerStatus.UNAVAILABLE)

    @staticmethod
    def _normalize_exam_component(value: Any) -> ExamComponent:
        normalized = str(getattr(value, "value", value)).lower()

        aliases = {
            "fg": ExamComponent.GENERAL_EDUCATION,
            "general_education": ExamComponent.GENERAL_EDUCATION,
            "ce": ExamComponent.SPECIFIC_COMPONENT,
            "specific_component": ExamComponent.SPECIFIC_COMPONENT,
            "unknown": ExamComponent.UNKNOWN,
        }

        return aliases.get(normalized, ExamComponent.UNKNOWN)

    @staticmethod
    def _close_component(component: Any) -> None:
        if component is None:
            return

        close = getattr(component, "close", None)

        if callable(close):
            try:
                close()
            except Exception:
                logger.exception(
                    "Erro ao encerrar componente %s.",
                    component.__class__.__name__,
                )


application = ExtractionApplication()


@asynccontextmanager
async def lifespan(app: FastAPI):
    application.start()

    try:
        yield
    finally:
        application.stop()


app = FastAPI(
    title="AcademicPass Extraction Service",
    description="Serviço de extração e estruturação de questões do ENADE.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", status_code=status.HTTP_200_OK)
def health() -> dict[str, Any]:
    if application._last_error:
        return {
            "status": "degraded",
            "service": "extraction-service",
            "error": application._last_error,
        }

    return {
        "status": "healthy",
        "service": "extraction-service",
        "consumer_started": application._started,
    }


@app.get("/ready", status_code=status.HTTP_200_OK)
def readiness(response: Response) -> dict[str, Any]:
    if not application._started:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return {
            "status": "not_ready",
            "service": "extraction-service",
        }

    return {
        "status": "ready",
        "service": "extraction-service",
    }


def main() -> None:
    import uvicorn

    uvicorn.run(
        "extraction.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=_env_int("PORT", 8082),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
