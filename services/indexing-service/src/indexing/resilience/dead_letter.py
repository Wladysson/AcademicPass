from __future__ import annotations

import json
import logging
import socket
import traceback
import uuid

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from confluent_kafka import KafkaException, Producer

from indexing.resilience.retry_policy import (
    NonRetryableError,
    RetryExhaustedError,
)

logger = logging.getLogger(__name__)


class DeadLetterError(Exception):
    """Erro base do tratamento de mensagens na DLQ."""


class DeadLetterPublicationError(DeadLetterError):
    """Falha ao publicar uma mensagem na DLQ."""


@dataclass(frozen=True, slots=True)
class DeadLetterResult:
    """Resultado do encaminhamento de uma mensagem para a DLQ."""

    published: bool
    event_id: str
    topic: str
    error_message: str | None = None
    published_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class DeadLetterEvent:
    """Representação de um evento de falha de indexação."""

    dead_letter_id: str
    original_event_id: str
    original_topic: str
    original_key: str | None
    occurred_at: datetime
    service: str
    error_type: str
    error_message: str
    retryable: bool
    stack_trace: str | None
    original_event: Mapping[str, Any]
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.dead_letter_id:
            raise ValueError("dead_letter_id é obrigatório.")

        if not self.original_event_id:
            raise ValueError("original_event_id é obrigatório.")

        if not self.original_topic:
            raise ValueError("original_topic é obrigatório.")

        if not self.error_type:
            raise ValueError("error_type é obrigatório.")

        if not self.error_message:
            raise ValueError("error_message é obrigatório.")

        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at deve possuir fuso horário.")

    def to_dict(self) -> dict[str, Any]:
        """Converte o evento para uma estrutura serializável."""

        return {
            "dead_letter_id": self.dead_letter_id,
            "original_event_id": self.original_event_id,
            "original_topic": self.original_topic,
            "original_key": self.original_key,
            "occurred_at": self.occurred_at.isoformat(),
            "service": self.service,
            "error": {
                "type": self.error_type,
                "message": self.error_message,
                "retryable": self.retryable,
                "stack_trace": self.stack_trace,
            },
            "original_event": dict(self.original_event),
            "metadata": dict(self.metadata),
        }


class DeadLetterHandler:
    """Encaminha eventos definitivamente rejeitados para a DLQ."""

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str = "enade.indexing.dlq",
        service_name: str = "indexing-service",
        client_id: str = "academicpass-indexing-dlq",
        security_protocol: str | None = None,
        sasl_mechanism: str | None = None,
        sasl_kerberos_service_name: str | None = None,
        sasl_kerberos_principal: str | None = None,
        sasl_kerberos_keytab: str | None = None,
        producer: Producer | None = None,
        publication_timeout_seconds: float = 10.0,
    ) -> None:
        if not bootstrap_servers and producer is None:
            raise ValueError("bootstrap_servers é obrigatório.")

        if not topic:
            raise ValueError("O tópico da DLQ é obrigatório.")

        if not service_name:
            raise ValueError("service_name é obrigatório.")

        if publication_timeout_seconds <= 0:
            raise ValueError(
                "publication_timeout_seconds deve ser positivo."
            )

        self.topic = topic
        self.service_name = service_name
        self.publication_timeout_seconds = publication_timeout_seconds
        self._producer_externo = producer is not None
        self._fechado = False

        if producer is not None:
            self.producer = producer
        else:
            config: dict[str, Any] = {
                "bootstrap.servers": bootstrap_servers,
                "client.id": client_id,
                "enable.idempotence": True,
                "acks": "all",
                "message.timeout.ms": int(
                    publication_timeout_seconds * 1000
                ),
            }

            if security_protocol:
                config["security.protocol"] = security_protocol

            if sasl_mechanism:
                config["sasl.mechanism"] = sasl_mechanism

            if sasl_kerberos_service_name:
                config["sasl.kerberos.service.name"] = (
                    sasl_kerberos_service_name
                )

            if sasl_kerberos_principal:
                config["sasl.kerberos.principal"] = (
                    sasl_kerberos_principal
                )

            if sasl_kerberos_keytab:
                config["sasl.kerberos.keytab"] = (
                    sasl_kerberos_keytab
                )

            self.producer = Producer(config)

    def encaminhar(
        self,
        original_event: Mapping[str, Any],
        error: Exception,
        *,
        original_topic: str = "enade.questions.structured",
        original_key: str | None = None,
        retryable: bool = False,
        metadata: Mapping[str, Any] | None = None,
        incluir_stack_trace: bool = True,
    ) -> DeadLetterResult:
        """Publica um evento com falha no tópico de DLQ."""

        self._validar_estado()

        if not isinstance(original_event, Mapping):
            raise TypeError("original_event deve ser um Mapping.")

        if not isinstance(error, Exception):
            raise TypeError("error deve ser uma Exception.")

        original_event_id = original_event.get("event_id")

        if not original_event_id:
            raise DeadLetterError(
                "O evento original não possui event_id."
            )

        if not original_topic:
            raise ValueError("original_topic é obrigatório.")

        stack_trace = (
            "".join(
                traceback.format_exception(
                    type(error),
                    error,
                    error.__traceback__,
                )
            )
            if incluir_stack_trace
            else None
        )

        evento = DeadLetterEvent(
            dead_letter_id=str(uuid.uuid4()),
            original_event_id=str(original_event_id),
            original_topic=original_topic,
            original_key=original_key,
            occurred_at=datetime.now(timezone.utc),
            service=self.service_name,
            error_type=type(error).__name__,
            error_message=str(error) or type(error).__name__,
            retryable=retryable,
            stack_trace=stack_trace,
            original_event=dict(original_event),
            metadata=dict(metadata or {}),
        )

        payload = json.dumps(
            evento.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            default=self._serializar_valor,
        ).encode("utf-8")

        delivery_errors: list[Exception] = []

        def delivery_callback(err: Any, message: Any) -> None:
            if err is not None:
                delivery_errors.append(
                    DeadLetterPublicationError(str(err))
                )

        try:
            self.producer.produce(
                topic=self.topic,
                key=str(original_event_id).encode("utf-8"),
                value=payload,
                headers=[
                    ("event_type", b"enade.indexing.failed"),
                    ("schema_version", b"1.0"),
                    (
                        "original_event_id",
                        str(original_event_id).encode("utf-8"),
                    ),
                ],
                on_delivery=delivery_callback,
            )

            remaining = self.producer.flush(
                self.publication_timeout_seconds
            )

            if remaining > 0:
                raise DeadLetterPublicationError(
                    f"{remaining} mensagem(ns) ainda aguardam confirmação "
                    "de publicação na DLQ."
                )

            if delivery_errors:
                raise delivery_errors[0]

            logger.warning(
                "Evento %s encaminhado para a DLQ %s. Erro: %s",
                original_event_id,
                self.topic,
                error,
            )

            return DeadLetterResult(
                published=True,
                event_id=str(original_event_id),
                topic=self.topic,
                published_at=datetime.now(timezone.utc),
            )

        except (KafkaException, DeadLetterPublicationError) as exc:
            logger.exception(
                "Falha ao encaminhar evento %s para a DLQ.",
                original_event_id,
            )

            raise DeadLetterPublicationError(
                f"Não foi possível publicar o evento "
                f"{original_event_id} na DLQ: {exc}"
            ) from exc

    def encaminhar_falha(
        self,
        original_event: Mapping[str, Any],
        error: Exception,
        *,
        original_topic: str = "enade.questions.structured",
        original_key: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> DeadLetterResult:
        """Encaminha uma falha após a política de retentativas."""

        retryable = not isinstance(error, NonRetryableError)

        if isinstance(error, RetryExhaustedError):
            retryable = True

        return self.encaminhar(
            original_event=original_event,
            error=error,
            original_topic=original_topic,
            original_key=original_key,
            retryable=retryable,
            metadata=metadata,
        )

    def fechar(self) -> None:
        """Finaliza o produtor quando ele pertence a este handler."""

        if self._fechado:
            return

        if not self._producer_externo:
            remaining = self.producer.flush(
                self.publication_timeout_seconds
            )

            if remaining > 0:
                raise DeadLetterPublicationError(
                    f"Não foi possível finalizar o produtor: "
                    f"{remaining} mensagem(ns) pendente(s)."
                )

        self._fechado = True

    def _validar_estado(self) -> None:
        if self._fechado:
            raise DeadLetterError(
                "O DeadLetterHandler já foi fechado."
            )

    @staticmethod
    def _serializar_valor(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()

        if hasattr(value, "value"):
            return value.value

        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")

        if hasattr(value, "__dict__"):
            return vars(value)

        raise TypeError(
            f"Tipo não serializável: {type(value).__name__}"
        )

    def __enter__(self) -> DeadLetterHandler:
        self._validar_estado()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb) -> None:
        self.fechar()
