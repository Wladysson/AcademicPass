from __future__ import annotations

import json
import logging
import uuid

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence

from confluent_kafka import KafkaException, Producer


logger = logging.getLogger(__name__)


class QuestionStructuredProducerError(Exception):
    """Erro durante a publicação de questões estruturadas."""


class QuestionSerializationError(QuestionStructuredProducerError):
    """Erro durante a serialização de uma questão."""


class QuestionPublicationError(QuestionStructuredProducerError):
    """Erro durante a publicação de uma questão no Kafka."""


@dataclass(frozen=True)
class PublicationResult:
    event_id: str
    topic: str
    partition: int | None
    offset: int | None
    published_at: datetime


class QuestionStructuredProducer:

    DEFAULT_TOPIC = "enade.questions.structured"
    EVENT_TYPE = "enade.question.structured"
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str = DEFAULT_TOPIC,
        client_id: str = "academicpass-extraction-service",
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
        self._pending_errors: list[Exception] = []
        self._closed = False

    def publicar(
        self,
        question: Any,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        """Publica uma questão estruturada e retorna o identificador do evento."""

        self._ensure_open()

        question_data = self._normalize_question(question)
        question_id = self._extract_question_id(question_data)

        event_id = str(uuid.uuid4())
        published_at = datetime.now(timezone.utc)

        event = {
            "event_id": event_id,
            "event_type": self.EVENT_TYPE,
            "schema_version": self.SCHEMA_VERSION,
            "published_at": published_at.isoformat(),
            "question_id": question_id,
            "metadata": self._normalize_value(dict(metadata or {})),
            "question": question_data,
        }

        payload = self._serialize(event)

        try:
            self._producer.produce(
                topic=self.topic,
                key=question_id.encode("utf-8"),
                value=payload,
                headers=[
                    ("event_type", self.EVENT_TYPE.encode("utf-8")),
                    (
                        "schema_version",
                        self.SCHEMA_VERSION.encode("utf-8"),
                    ),
                    ("event_id", event_id.encode("utf-8")),
                ],
                callback=self._delivery_callback,
            )

            self._producer.poll(0)

        except BufferError as error:
            raise QuestionPublicationError(
                "O buffer local do produtor Kafka está cheio."
            ) from error

        except KafkaException as error:
            raise QuestionPublicationError(
                "Falha ao enviar questão para o Kafka."
            ) from error

        except Exception as error:
            raise QuestionPublicationError(
                "Erro inesperado durante o envio da questão."
            ) from error

        return event_id

    def publicar_lote(
        self,
        questions: Sequence[Any],
        metadata: Mapping[str, Any] | None = None,
    ) -> list[str]:

        event_ids: list[str] = []

        for question in questions:
            event_ids.append(
                self.publicar(
                    question=question,
                    metadata=metadata,
                )
            )

        return event_ids

    def aguardar_publicacao(
        self,
        timeout: float | None = None,
    ) -> int:

        self._ensure_open()

        try:
            remaining = self._producer.flush(
                timeout if timeout is not None else self.flush_timeout
            )

        except KafkaException as error:
            raise QuestionPublicationError(
                "Falha ao aguardar a publicação das mensagens Kafka."
            ) from error

        if self._pending_errors:
            error = self._pending_errors.pop(0)

            raise QuestionPublicationError(
                "Uma ou mais questões não foram entregues ao Kafka."
            ) from error

        return remaining

    def publicar_e_aguardar(
        self,
        question: Any,
        metadata: Mapping[str, Any] | None = None,
    ) -> PublicationResult:
        """Publica uma questão e aguarda sua confirmação de entrega."""

        event_id = self.publicar(question, metadata)
        remaining = self.aguardar_publicacao()

        if remaining:
            raise QuestionPublicationError(
                f"{remaining} mensagem(ns) permanecem pendentes."
            )

        return PublicationResult(
            event_id=event_id,
            topic=self.topic,
            partition=None,
            offset=None,
            published_at=datetime.now(timezone.utc),
        )

    def _delivery_callback(
        self,
        error: Any,
        message: Any,
    ) -> None:
        if error is not None:
            self._pending_errors.append(error)

            logger.error(
                "Falha na entrega da questão ao Kafka: %s",
                error,
            )
            return

        logger.debug(
            "Questão entregue ao tópico %s, partição %s, offset %s.",
            message.topic(),
            message.partition(),
            message.offset(),
        )

    @classmethod
    def _normalize_question(cls, question: Any) -> dict[str, Any]:
        if is_dataclass(question) and not isinstance(question, type):
            question = asdict(question)

        elif hasattr(question, "model_dump"):
            question = question.model_dump(mode="python")

        elif hasattr(question, "dict") and callable(question.dict):
            question = question.dict()

        if not isinstance(question, Mapping):
            raise QuestionSerializationError(
                "A questão deve ser um objeto estruturado."
            )

        normalized = cls._normalize_value(dict(question))

        if not isinstance(normalized, dict):
            raise QuestionSerializationError(
                "Não foi possível normalizar a questão."
            )

        return normalized

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

        raise QuestionSerializationError(
            f"Tipo de dado não suportado: {type(value).__name__}."
        )

    @staticmethod
    def _extract_question_id(question: Mapping[str, Any]) -> str:
        question_id = (
            question.get("question_id")
            or question.get("id")
        )

        if not isinstance(question_id, str) or not question_id.strip():
            raise QuestionSerializationError(
                "A questão precisa possuir um question_id ou id válido."
            )

        return question_id.strip()

    @staticmethod
    def _serialize(event: Mapping[str, Any]) -> bytes:
        try:
            return json.dumps(
                event,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")

        except (TypeError, ValueError) as error:
            raise QuestionSerializationError(
                "Não foi possível serializar o evento da questão."
            ) from error

    def _ensure_open(self) -> None:
        if self._closed:
            raise QuestionStructuredProducerError(
                "O produtor Kafka já foi encerrado."
            )

    def close(self) -> None:
        if self._closed:
            return

        if self._owns_producer:
            self.aguardar_publicacao()

        self._closed = True

    def __enter__(self) -> QuestionStructuredProducer:
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        self.close()
