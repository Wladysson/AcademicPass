from __future__ import annotations

import json
import logging
import uuid

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Mapping

from confluent_kafka import KafkaException, Producer


logger = logging.getLogger(__name__)


class ExtractionErrorProducerError(Exception):
    """Erro durante a publicação de falhas de extração."""


class ExtractionErrorSerializationError(ExtractionErrorProducerError):
    """Erro durante a serialização de um evento de falha."""


class ExtractionErrorPublicationError(ExtractionErrorProducerError):
    """Erro durante a publicação de uma falha no Kafka."""


@dataclass(frozen=True)
class ExtractionErrorEvent:
    event_id: str
    original_event_id: str
    storage_key: str
    error_type: str
    error_message: str
    occurred_at: datetime
    attempt: int
    retryable: bool
    stack_trace: str | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("O identificador do evento é obrigatório.")

        if not self.original_event_id.strip():
            raise ValueError(
                "O identificador do evento original é obrigatório."
            )

        if not self.storage_key.strip():
            raise ValueError("O storage_key é obrigatório.")

        if not self.error_type.strip():
            raise ValueError("O tipo do erro é obrigatório.")

        if not self.error_message.strip():
            raise ValueError("A mensagem do erro é obrigatória.")

        if self.attempt < 1:
            raise ValueError("O número da tentativa deve ser positivo.")

        if self.occurred_at.tzinfo is None:
            raise ValueError(
                "A data da ocorrência deve possuir fuso horário."
            )


@dataclass(frozen=True)
class ErrorPublicationResult:
    event_id: str
    topic: str
    published_at: datetime


class ExtractionErrorProducer:

    DEFAULT_TOPIC = "enade.extraction.dlq"
    EVENT_TYPE = "enade.extraction.failed"
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str = DEFAULT_TOPIC,
        client_id: str = "academicpass-extraction-dlq-producer",
        security_protocol: str | None = None,
        sasl_mechanism: str | None = None,
        sasl_username: str | None = None,
        sasl_password: str | None = None,
        kerberos_service_name: str | None = None,
        additional_config: Mapping[str, Any] | None = None,
        producer: Producer | None = None,
        flush_timeout: float = 30.0,
    ) -> None:
        if not bootstrap_servers.strip():
            raise ValueError("Os servidores Kafka são obrigatórios.")

        if not topic.strip():
            raise ValueError("O tópico Kafka é obrigatório.")

        if flush_timeout <= 0:
            raise ValueError("O timeout de publicação deve ser positivo.")

        self.topic = topic
        self.flush_timeout = flush_timeout
        self._owns_producer = producer is None
        self._closed = False
        self._pending_errors: list[Exception] = []

        config: dict[str, Any] = {
            "bootstrap.servers": bootstrap_servers,
            "client.id": client_id,
            "enable.idempotence": True,
            "acks": "all",
            "retries": 10,
            "max.in.flight.requests.per.connection": 5,
        }

        if security_protocol:
            config["security.protocol"] = security_protocol

        if sasl_mechanism:
            config["sasl.mechanism"] = sasl_mechanism

        if sasl_username:
            config["sasl.username"] = sasl_username

        if sasl_password:
            config["sasl.password"] = sasl_password

        if kerberos_service_name:
            config["sasl.kerberos.service.name"] = (
                kerberos_service_name
            )

        if additional_config:
            config.update(additional_config)

        self._producer = producer or Producer(config)

    def publicar(
        self,
        original_event_id: str,
        storage_key: str,
        error: Exception,
        attempt: int = 1,
        retryable: bool = False,
        stack_trace: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        """Publica uma falha de processamento na DLQ."""

        self._ensure_open()

        if not original_event_id.strip():
            raise ValueError(
                "O identificador do evento original é obrigatório."
            )

        if not storage_key.strip():
            raise ValueError("O storage_key é obrigatório.")

        if attempt < 1:
            raise ValueError("O número da tentativa deve ser positivo.")

        event = ExtractionErrorEvent(
            event_id=str(uuid.uuid4()),
            original_event_id=original_event_id,
            storage_key=storage_key,
            error_type=type(error).__name__,
            error_message=str(error) or "Erro sem mensagem.",
            occurred_at=datetime.now(timezone.utc),
            attempt=attempt,
            retryable=retryable,
            stack_trace=stack_trace,
            metadata=metadata,
        )

        payload = self._serialize(event)

        try:
            self._producer.produce(
                topic=self.topic,
                key=storage_key.encode("utf-8"),
                value=payload,
                headers=[
                    (
                        "event_type",
                        self.EVENT_TYPE.encode("utf-8"),
                    ),
                    (
                        "schema_version",
                        self.SCHEMA_VERSION.encode("utf-8"),
                    ),
                    (
                        "event_id",
                        event.event_id.encode("utf-8"),
                    ),
                    (
                        "original_event_id",
                        original_event_id.encode("utf-8"),
                    ),
                ],
                callback=self._delivery_callback,
            )

            self._producer.poll(0)

        except BufferError as error:
            raise ExtractionErrorPublicationError(
                "O buffer local do produtor Kafka está cheio."
            ) from error

        except KafkaException as error:
            raise ExtractionErrorPublicationError(
                "Falha ao publicar o evento de erro na DLQ."
            ) from error

        except Exception as error:
            raise ExtractionErrorPublicationError(
                "Erro inesperado durante a publicação na DLQ."
            ) from error

        logger.info(
            "Evento de falha %s encaminhado para publicação na DLQ.",
            event.event_id,
        )

        return event.event_id

    def publicar_e_aguardar(
        self,
        original_event_id: str,
        storage_key: str,
        error: Exception,
        attempt: int = 1,
        retryable: bool = False,
        stack_trace: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ErrorPublicationResult:

        event_id = self.publicar(
            original_event_id=original_event_id,
            storage_key=storage_key,
            error=error,
            attempt=attempt,
            retryable=retryable,
            stack_trace=stack_trace,
            metadata=metadata,
        )

        remaining = self.aguardar_publicacao()

        if remaining:
            raise ExtractionErrorPublicationError(
                f"{remaining} mensagem(ns) permanecem pendentes."
            )

        return ErrorPublicationResult(
            event_id=event_id,
            topic=self.topic,
            published_at=datetime.now(timezone.utc),
        )

    def aguardar_publicacao(
        self,
        timeout: float | None = None,
    ) -> int:
        """Aguarda a entrega das mensagens pendentes."""

        self._ensure_open()

        try:
            remaining = self._producer.flush(
                timeout if timeout is not None else self.flush_timeout
            )

        except KafkaException as error:
            raise ExtractionErrorPublicationError(
                "Falha ao aguardar a entrega das mensagens da DLQ."
            ) from error

        if self._pending_errors:
            error = self._pending_errors.pop(0)

            raise ExtractionErrorPublicationError(
                "Uma ou mais mensagens não foram entregues à DLQ."
            ) from error

        return remaining

    def _delivery_callback(
        self,
        error: Any,
        message: Any,
    ) -> None:
        if error is not None:
            self._pending_errors.append(error)

            logger.error(
                "Falha na entrega de evento à DLQ: %s",
                error,
            )
            return

        logger.debug(
            "Evento de falha entregue ao tópico %s, "
            "partição %s, offset %s.",
            message.topic(),
            message.partition(),
            message.offset(),
        )

    @classmethod
    def _serialize(
        cls,
        event: ExtractionErrorEvent,
    ) -> bytes:
        try:
            event_data = asdict(event)

            payload = {
                "event_id": event_data["event_id"],
                "event_type": cls.EVENT_TYPE,
                "schema_version": cls.SCHEMA_VERSION,
                "occurred_at": event_data["occurred_at"].isoformat(),
                "original_event_id": event_data["original_event_id"],
                "storage_key": event_data["storage_key"],
                "error": {
                    "type": event_data["error_type"],
                    "message": event_data["error_message"],
                    "attempt": event_data["attempt"],
                    "retryable": event_data["retryable"],
                    "stack_trace": event_data["stack_trace"],
                },
                "metadata": cls._normalize_value(
                    event_data["metadata"] or {}
                ),
            }

            return json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")

        except (TypeError, ValueError) as error:
            raise ExtractionErrorSerializationError(
                "Não foi possível serializar o evento de falha."
            ) from error

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        if is_dataclass(value) and not isinstance(value, type):
            return cls._normalize_value(asdict(value))

        if isinstance(value, Enum):
            return value.value

        if isinstance(value, (datetime, date)):
            return value.isoformat()

        if isinstance(value, Mapping):
            return {
                str(key): cls._normalize_value(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple)):
            return [
                cls._normalize_value(item)
                for item in value
            ]

        if value is None or isinstance(
            value,
            (str, int, float, bool),
        ):
            return value

        raise ExtractionErrorSerializationError(
            f"Tipo de dado não suportado: {type(value).__name__}."
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise ExtractionErrorProducerError(
                "O produtor Kafka já foi encerrado."
            )

    def close(self) -> None:
        if self._closed:
            return

        if self._owns_producer:
            self.aguardar_publicacao()

        self._closed = True

    def __enter__(self) -> ExtractionErrorProducer:
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        self.close()
