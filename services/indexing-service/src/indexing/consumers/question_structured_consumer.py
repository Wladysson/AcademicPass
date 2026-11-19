from __future__ import annotations

import json
import logging
import signal
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from confluent_kafka import Consumer, KafkaError, KafkaException, Message


logger = logging.getLogger(__name__)

QUESTION_STRUCTURED_TOPIC = "enade.questions.structured"


class QuestionStructuredConsumerError(Exception):
    """Erro durante o consumo de eventos de questões estruturadas."""


class InvalidQuestionEventError(QuestionStructuredConsumerError):
    """Evento recebido com estrutura inválida."""


@dataclass(frozen=True, slots=True)
class ConsumedQuestionEvent:
    """Representa um evento recebido do Kafka."""

    topic: str
    partition: int
    offset: int
    key: str | None
    payload: dict[str, Any]
    received_at: datetime

    @property
    def event_id(self) -> str | None:
        value = self.payload.get("event_id")
        return str(value) if value is not None else None


QuestionEventHandler = Callable[[ConsumedQuestionEvent], None]


class QuestionStructuredConsumer:
    """Consome eventos estruturados e confirma offsets após processamento."""

    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        topic: str = QUESTION_STRUCTURED_TOPIC,
        client_id: str = "academicpass-indexing-consumer",
        auto_offset_reset: str = "earliest",
        poll_timeout_seconds: float = 1.0,
        max_poll_interval_ms: int = 300000,
        session_timeout_ms: int = 45000,
        security_protocol: str | None = None,
        sasl_mechanism: str | None = None,
        sasl_username: str | None = None,
        sasl_password: str | None = None,
        sasl_kerberos_service_name: str | None = None,
        additional_config: Mapping[str, Any] | None = None,
    ) -> None:
        if not bootstrap_servers.strip():
            raise ValueError("bootstrap_servers não pode ser vazio.")

        if not group_id.strip():
            raise ValueError("group_id não pode ser vazio.")

        if not topic.strip():
            raise ValueError("topic não pode ser vazio.")

        if poll_timeout_seconds <= 0:
            raise ValueError("poll_timeout_seconds deve ser maior que zero.")

        self._topic = topic
        self._poll_timeout_seconds = poll_timeout_seconds
        self._handler: QuestionEventHandler | None = None
        self._running = threading.Event()
        self._closed = False

        config: dict[str, Any] = {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "client.id": client_id,
            "auto.offset.reset": auto_offset_reset,
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
            "max.poll.interval.ms": max_poll_interval_ms,
            "session.timeout.ms": session_timeout_ms,
        }

        if security_protocol:
            config["security.protocol"] = security_protocol

        if sasl_mechanism:
            config["sasl.mechanism"] = sasl_mechanism

        if sasl_username:
            config["sasl.username"] = sasl_username

        if sasl_password:
            config["sasl.password"] = sasl_password

        if sasl_kerberos_service_name:
            config["sasl.kerberos.service.name"] = (
                sasl_kerberos_service_name
            )

        if additional_config:
            protected_keys = {
                "bootstrap.servers",
                "group.id",
                "enable.auto.commit",
                "enable.auto.offset.store",
            }

            conflicting_keys = protected_keys.intersection(
                additional_config
            )

            if conflicting_keys:
                raise ValueError(
                    "Configurações protegidas não podem ser sobrescritas: "
                    f"{', '.join(sorted(conflicting_keys))}"
                )

            config.update(additional_config)

        try:
            self._consumer = Consumer(config)
            self._consumer.subscribe([self._topic])
        except KafkaException as exc:
            raise QuestionStructuredConsumerError(
                "Não foi possível inicializar o consumidor Kafka."
            ) from exc

    def registrar_handler(self, handler: QuestionEventHandler) -> None:
        """Registra a função responsável pelo processamento dos eventos."""
        if not callable(handler):
            raise TypeError("O handler deve ser uma função executável.")

        self._handler = handler

    def consumir(self) -> None:
        """Inicia o loop de consumo até que seja solicitado o encerramento."""
        if self._closed:
            raise QuestionStructuredConsumerError(
                "O consumidor já foi encerrado."
            )

        if self._handler is None:
            raise QuestionStructuredConsumerError(
                "Nenhum handler foi registrado."
            )

        self._running.set()
        logger.info("Consumindo eventos do tópico %s.", self._topic)

        try:
            while self._running.is_set():
                message = self._consumer.poll(
                    self._poll_timeout_seconds
                )

                if message is None:
                    continue

                if message.error():
                    if message.error().code() == KafkaError._PARTITION_EOF:
                        continue

                    raise QuestionStructuredConsumerError(
                        f"Erro recebido do Kafka: {message.error()}"
                    )

                self.consumir_mensagem(message)

        except (KafkaException, QuestionStructuredConsumerError):
            logger.exception(
                "O loop de consumo foi interrompido por um erro."
            )
            raise
        finally:
            self._running.clear()

    def consumir_mensagem(self, message: Message) -> ConsumedQuestionEvent:
        """Decodifica, processa e confirma uma mensagem individual."""
        if self._handler is None:
            raise QuestionStructuredConsumerError(
                "Nenhum handler foi registrado."
            )

        if message.error():
            raise QuestionStructuredConsumerError(
                f"Não é possível processar uma mensagem com erro: "
                f"{message.error()}"
            )

        payload = self._decodificar_payload(message.value())

        event = ConsumedQuestionEvent(
            topic=message.topic(),
            partition=message.partition(),
            offset=message.offset(),
            key=self._decodificar_key(message.key()),
            payload=payload,
            received_at=datetime.now(timezone.utc),
        )

        try:
            self._handler(event)
        except Exception as exc:
            logger.exception(
                "Falha ao processar evento %s na partição %s, offset %s.",
                event.event_id,
                event.partition,
                event.offset,
            )
            raise QuestionStructuredConsumerError(
                "O handler não conseguiu processar o evento. "
                "O offset não será confirmado."
            ) from exc

        self._confirmar_offset(message)

        logger.debug(
            "Evento %s processado e confirmado. Partição: %s, offset: %s.",
            event.event_id,
            event.partition,
            event.offset,
        )

        return event

    def _decodificar_payload(self, value: bytes | None) -> dict[str, Any]:
        if not value:
            raise InvalidQuestionEventError(
                "A mensagem Kafka está vazia."
            )

        try:
            payload = json.loads(value.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidQuestionEventError(
                "A mensagem não contém um JSON UTF-8 válido."
            ) from exc

        if not isinstance(payload, dict):
            raise InvalidQuestionEventError(
                "O evento deve ser um objeto JSON."
            )

        event_type = payload.get("event_type")

        if event_type != QUESTION_STRUCTURED_TOPIC:
            raise InvalidQuestionEventError(
                f"Tipo de evento inválido: {event_type!r}."
            )

        if not isinstance(payload.get("event_id"), str):
            raise InvalidQuestionEventError(
                "O evento precisa conter um event_id textual."
            )

        if not isinstance(payload.get("question_id"), str):
            raise InvalidQuestionEventError(
                "O evento precisa conter um question_id textual."
            )

        if not isinstance(payload.get("question"), dict):
            raise InvalidQuestionEventError(
                "O evento precisa conter o objeto question."
            )

        return payload

    @staticmethod
    def _decodificar_key(key: bytes | None) -> str | None:
        if key is None:
            return None

        try:
            return key.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidQuestionEventError(
                "A chave Kafka não contém UTF-8 válido."
            ) from exc

    def _confirmar_offset(self, message: Message) -> None:
        """Confirma somente a mensagem cujo processamento foi concluído."""
        try:
            self._consumer.commit(
                message=message,
                asynchronous=False,
            )
        except KafkaException as exc:
            raise QuestionStructuredConsumerError(
                "Falha ao confirmar o offset da mensagem."
            ) from exc

    def parar(self) -> None:
        """Solicita o encerramento do loop de consumo."""
        self._running.clear()

    def instalar_sinais_de_encerramento(self) -> None:
        """Registra handlers para SIGINT e SIGTERM."""
        signal.signal(signal.SIGINT, self._tratar_sinal)
        signal.signal(signal.SIGTERM, self._tratar_sinal)

    def _tratar_sinal(self, signum: int, frame: Any) -> None:
        logger.info(
            "Sinal %s recebido. Encerrando consumo.",
            signum,
        )
        self.parar()

    def fechar(self) -> None:
        """Encerra a conexão com o Kafka."""
        if self._closed:
            return

        self.parar()

        try:
            self._consumer.close()
        except KafkaException as exc:
            raise QuestionStructuredConsumerError(
                "Falha ao encerrar o consumidor Kafka."
            ) from exc
        finally:
            self._closed = True

        logger.info("Consumidor Kafka encerrado.")

    def __enter__(self) -> QuestionStructuredConsumer:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        self.fechar()
