from __future__ import annotations

import logging
import time
from typing import Any

from confluent_kafka import KafkaError, KafkaException, Producer
from ingestion.events.pdf_discovered_event import PdfDiscoveredEvent


logger = logging.getLogger(__name__)


class KafkaProducerError(Exception):
    """Representa falhas na publicação de eventos no Kafka"""


class KafkaProducerClient:

    DEFAULT_TOPIC = "enade.pdfs.discovered"

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str = DEFAULT_TOPIC,
        client_id: str = "academicpass-ingestion-service",
        delivery_timeout_seconds: float = 30.0,
        request_timeout_ms: int = 10000,
        security_config: dict[str, Any] | None = None,
        additional_config: dict[str, Any] | None = None,
    ) -> None:
        if not bootstrap_servers.strip():
            raise ValueError("Os servidores Kafka devem ser informados.")

        if not topic.strip():
            raise ValueError("O tópico Kafka deve ser informado.")

        if not client_id.strip():
            raise ValueError("O identificador do produtor deve ser informado.")

        if delivery_timeout_seconds <= 0:
            raise ValueError("O timeout de entrega deve ser positivo.")

        if request_timeout_ms <= 0:
            raise ValueError("O timeout de requisição deve ser positivo.")

        self._topic = topic
        self._delivery_timeout_seconds = delivery_timeout_seconds
        self._closed = False

        producer_config: dict[str, Any] = {
            "bootstrap.servers": bootstrap_servers,
            "client.id": client_id,
            "acks": "all",
            "enable.idempotence": True,
            "retries": 2147483647,
            "request.timeout.ms": request_timeout_ms,
            "delivery.timeout.ms": int(delivery_timeout_seconds * 1000),
        }

        if security_config:
            producer_config.update(security_config)

        if additional_config:
            producer_config.update(additional_config)

        # Mantém as garantias de entrega exigidas pelo serviço.
        producer_config["acks"] = "all"
        producer_config["enable.idempotence"] = True

        try:
            self._producer = Producer(producer_config)
        except (KafkaException, ValueError, TypeError) as exc:
            raise KafkaProducerError(
                "Não foi possível inicializar o produtor Kafka."
            ) from exc

    def publicar(self, event: PdfDiscoveredEvent) -> None:

        self._validar_evento(event)
        self._verificar_aberto()

        delivery_result: dict[str, Any] = {
            "completed": False,
            "error": None,
        }

        def on_delivery(
            error: KafkaError | None,
            message: Any,
        ) -> None:
            delivery_result["completed"] = True
            delivery_result["error"] = error

            if error is None:
                logger.info(
                    "Evento publicado no Kafka. topic=%s partition=%s offset=%s",
                    message.topic(),
                    message.partition(),
                    message.offset(),
                )

        try:
            self._producer.produce(
                topic=self._topic,
                key=event.storage_key.encode("utf-8"),
                value=event.to_json().encode("utf-8"),
                headers={
                    "event_type": PdfDiscoveredEvent.EVENT_TYPE.encode("utf-8"),
                    "schema_version": event.schema_version.encode("utf-8"),
                    "event_id": event.event_id.encode("utf-8"),
                },
                on_delivery=on_delivery,
            )

            deadline = time.monotonic() + self._delivery_timeout_seconds

            while not delivery_result["completed"]:
                remaining = deadline - time.monotonic()

                if remaining <= 0:
                    raise KafkaProducerError(
                        "Tempo limite excedido aguardando a entrega do evento."
                    )

                self._producer.poll(min(remaining, 0.1))

            if delivery_result["error"] is not None:
                raise KafkaProducerError(
                    "O broker Kafka não confirmou a entrega do evento."
                ) from KafkaException(delivery_result["error"])

        except KafkaProducerError:
            raise
        except (KafkaException, BufferError, ValueError, TypeError) as exc:
            raise KafkaProducerError(
                "Falha ao publicar evento no Kafka."
            ) from exc

    def publicar_lote(
        self,
        events: list[PdfDiscoveredEvent],
    ) -> None:

        for event in events:
            self.publicar(event)

    def flush(self, timeout_seconds: float | None = None) -> None:

        self._verificar_aberto()

        timeout = (
            self._delivery_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )

        if timeout <= 0:
            raise ValueError("O timeout de flush deve ser positivo.")

        try:
            pending_messages = self._producer.flush(timeout)

            if pending_messages > 0:
                raise KafkaProducerError(
                    f"Existem {pending_messages} mensagem(ns) pendente(s) no Kafka."
                )
        except KafkaProducerError:
            raise
        except KafkaException as exc:
            raise KafkaProducerError(
                "Falha ao finalizar as mensagens pendentes no Kafka."
            ) from exc

    def close(self) -> None:

        if self._closed:
            return

        try:
            pending_messages = self._producer.flush(
                self._delivery_timeout_seconds
            )

            if pending_messages > 0:
                raise KafkaProducerError(
                    "Não foi possível entregar todas as mensagens antes do encerramento."
                )
        finally:
            self._closed = True

    def _validar_evento(self, event: PdfDiscoveredEvent) -> None:
        if not isinstance(event, PdfDiscoveredEvent):
            raise TypeError(
                "O produtor aceita somente instâncias de PdfDiscoveredEvent."
            )

    def _verificar_aberto(self) -> None:
        if self._closed:
            raise KafkaProducerError(
                "O produtor Kafka já foi encerrado."
            )

    def __enter__(self) -> KafkaProducerClient:
        self._verificar_aberto()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        self.close()
