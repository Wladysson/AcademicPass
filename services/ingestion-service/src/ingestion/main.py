from __future__ import annotations

import logging
import time

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field
from starlette.responses import Response

from ingestion.collectors.enade_downloader import (
    DocumentType,
    EnaDeDownloader,
)
from ingestion.config import IngestionSettings, get_settings
from ingestion.events.kafka_producer import (
    KafkaProducerClient,
    KafkaProducerError,
)
from ingestion.events.pdf_discovered_event import (
    PdfDiscoveredEvent,
    PdfDocumentMetadata,
    PdfDocumentType,
)
from ingestion.observability.metrics import IngestionMetrics
from ingestion.storage.local_volume_pdf_storage import LocalVolumePdfStorage
from ingestion.storage.minio_pdf_storage import MinioPdfStorage
from ingestion.storage.pdf_storage import PdfStorage, PdfStorageError


logger = logging.getLogger(__name__)


class IngestionRequest(BaseModel):
    """Dados necessários para iniciar a ingestão de um documento ENADE."""

    source_id: str = Field(min_length=1, max_length=100)
    source_name: str = Field(min_length=1, max_length=200)
    course_code: str = Field(min_length=1, max_length=50)
    course_name: str = Field(min_length=1, max_length=200)
    edition_year: int = Field(ge=2004)
    document_type: Literal["exam", "answer_key", "guideline"]
    source_url: str = Field(min_length=1, max_length=2048)


class IngestionResponse(BaseModel):

    event_id: str
    storage_key: str
    checksum: str
    size_bytes: int
    topic: str
    status: str = "published"


class IngestionService:

    def __init__(
        self,
        downloader: EnaDeDownloader,
        storage: PdfStorage,
        kafka_producer: KafkaProducerClient,
        metrics: IngestionMetrics,
        kafka_topic: str,
    ) -> None:
        self._downloader = downloader
        self._storage = storage
        self._kafka_producer = kafka_producer
        self._metrics = metrics
        self._kafka_topic = kafka_topic

    def ingerir(self, request: IngestionRequest) -> IngestionResponse:
        """Executa o fluxo completo de ingestão de um documento."""

        document_type = request.document_type
        started_at = time.perf_counter()
        current_stage = "download"

        try:
            document = self._downloader.download(request.source_url)

            download_duration = time.perf_counter() - started_at

            self._metrics.registrar_download_concluido(
                document_type=document_type,
                duration_seconds=download_duration,
                size_bytes=document.size_bytes,
            )

            current_stage = "storage"

            storage_metadata = self._storage.salvar(
                file_name=document.file_name,
                content=document.content,
                checksum=document.checksum,
            )

            current_stage = "event"

            event_metadata = PdfDocumentMetadata(
                source_id=request.source_id,
                source_name=request.source_name,
                course_code=request.course_code,
                course_name=request.course_name,
                edition_year=request.edition_year,
                document_type=PdfDocumentType(document_type),
                source_url=request.source_url,
            )

            event = PdfDiscoveredEvent(
                event_id=str(uuid4()),
                storage_key=storage_metadata.storage_key,
                checksum=storage_metadata.checksum,
                size_bytes=storage_metadata.size_bytes,
                file_name=storage_metadata.file_name,
                content_type=storage_metadata.content_type,
                metadata=event_metadata,
                discovered_at=datetime.now(timezone.utc),
            )

            current_stage = "kafka"

            self._kafka_producer.publicar(event)

            logger.info(
                "Documento ingerido e evento publicado. "
                "event_id=%s document_type=%s",
                event.event_id,
                document_type,
            )

            return IngestionResponse(
                event_id=event.event_id,
                storage_key=storage_metadata.storage_key,
                checksum=storage_metadata.checksum,
                size_bytes=storage_metadata.size_bytes,
                topic=self._kafka_topic,
            )

        except Exception as exc:
            if current_stage == "download":
                reason = self._classificar_falha_download(exc)

                self._metrics.registrar_falha_download(
                    document_type=document_type,
                    reason=reason,
                    duration_seconds=time.perf_counter() - started_at,
                )
            elif current_stage == "storage":
                self._metrics.registrar_falha_download(
                    document_type=document_type,
                    reason="storage",
                )

            logger.exception(
                "Falha durante a ingestão do documento. stage=%s "
                "document_type=%s",
                current_stage,
                document_type,
            )

            raise

    @staticmethod
    def _classificar_falha_download(exc: Exception) -> str:

        exception_name = type(exc).__name__.lower()

        if "timeout" in exception_name:
            return "timeout"

        if any(
            term in exception_name
            for term in ("network", "connection", "protocol")
        ):
            return "network"

        if any(
            term in exception_name
            for term in ("validation", "invalid", "url")
        ):
            return "validation"

        return "unknown"

    def close(self) -> None:

        errors: list[Exception] = []

        for component in (
            self._kafka_producer,
            self._downloader,
        ):
            try:
                component.close()
            except Exception as exc:
                errors.append(exc)
                logger.exception(
                    "Falha ao encerrar componente do ingestion-service."
                )

        if errors:
            raise RuntimeError(
                "Um ou mais componentes não foram encerrados corretamente."
            ) from errors[0]


def _criar_armazenamento(settings: IngestionSettings) -> PdfStorage:

    if settings.storage_backend == "minio":
        return MinioPdfStorage(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key.get_secret_value(),
            secret_key=settings.minio_secret_key.get_secret_value(),
            bucket_name=settings.minio_bucket_name,
            secure=settings.minio_secure,
            max_file_size_mb=settings.storage_max_file_size_mb,
            region=settings.minio_region,
        )

    if settings.storage_backend == "local":
        return LocalVolumePdfStorage(
            storage_path=settings.local_storage_path,
            max_file_size_mb=settings.storage_max_file_size_mb,
        )

    raise ValueError(
        f"Backend de armazenamento não suportado: {settings.storage_backend}."
    )


def _criar_servico(
    settings: IngestionSettings,
    metrics: IngestionMetrics,
) -> IngestionService:

    downloader = EnaDeDownloader(
        timeout_seconds=settings.downloader_timeout_seconds,
        max_file_size_mb=settings.downloader_max_file_size_mb,
        max_retries=settings.downloader_max_retries,
        chunk_size=settings.downloader_chunk_size,
        allowed_domains=settings.allowed_domains,
    )

    try:
        storage = _criar_armazenamento(settings)

        kafka_producer = KafkaProducerClient(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            topic=settings.kafka_topic,
            client_id=settings.kafka_client_id,
            delivery_timeout_seconds=settings.kafka_delivery_timeout_seconds,
            request_timeout_ms=settings.kafka_request_timeout_ms,
            security_config=settings.kafka_security_config,
        )

    except Exception:
        downloader.close()
        raise

    return IngestionService(
        downloader=downloader,
        storage=storage,
        kafka_producer=kafka_producer,
        metrics=metrics,
        kafka_topic=settings.kafka_topic,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):

    settings = get_settings()

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    metrics = IngestionMetrics()
    service = _criar_servico(settings, metrics)

    app.state.settings = settings
    app.state.metrics = metrics
    app.state.ingestion_service = service

    logger.info(
        "Ingestion-service iniciado. environment=%s storage_backend=%s",
        settings.app_environment,
        settings.storage_backend,
    )

    try:
        yield
    finally:
        try:
            service.close()
        except Exception:
            logger.exception(
                "Falha durante o encerramento do ingestion-service."
            )

        logger.info("Ingestion-service encerrado.")


app = FastAPI(
    title="AcademicPass Ingestion Service",
    description=(
        "Serviço responsável pela descoberta, download, armazenamento "
        "e publicação de eventos de documentos ENADE"
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.get(
    "/health",
    tags=["Health"],
    status_code=status.HTTP_200_OK,
)
def health() -> dict[str, str]:
    """Verifica se a aplicação está respondendo"""

    return {
        "service": "academicpass-ingestion-service",
        "status": "healthy",
    }


@app.post(
    "/api/v1/ingestion",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Ingestion"],
)
def ingerir_documento(
    payload: IngestionRequest,
    request: Request,
) -> IngestionResponse:
    """Inicia a ingestão de um documento ENADE."""

    service: IngestionService = request.app.state.ingestion_service

    try:
        return service.ingerir(payload)

    except KafkaProducerError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível confirmar a publicação do evento no Kafka.",
        ) from exc

    except PdfStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível armazenar o documento.",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Falha durante o processamento do documento de origem.",
        ) from exc


@app.get(
    "/metrics",
    tags=["Observability"],
    include_in_schema=False,
)
def obter_metricas(request: Request) -> Response:
    """Expõe as métricas no formato de scraping do Prometheus."""

    settings: IngestionSettings = request.app.state.settings

    if not settings.metrics_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A exposição de métricas está desabilitada.",
        )

    metrics: IngestionMetrics = request.app.state.metrics

    return Response(
        content=metrics.obter_metricas(),
        media_type=metrics.content_type,
    )
