from __future__ import annotations

import json
import logging
import signal
import threading
from collections.abc import Callable
from typing import Any

from confluent_kafka import Consumer, KafkaError, KafkaException, Message

logger = logging.getLogger(__name__)


class PdfDiscoveredConsumerError(Exception):
    """Erro relacionado ao consumo de eventos de PDFs descobertos"""


class PdfDiscoveredConsumer:
    EVENT_TYPE = "enade.pdf.discovered"

    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        topic: str = "enade.pdfs.discovered",
        client_id: str = "academicpass-extraction-service",
        auto_offset_reset: str = "earliest",
        enable_auto_commit: bool = False,
        poll_timeout_seconds: float = 1.0,
        security_config: dict[str, Any] | None = None,
        additional_config: dict[str, Any] | None = None,
    ) -> None:
        if not bootstrap_servers.strip():
            raise ValueError("Os servidores Kafka são obrigatórios.")

        if not group_id.strip():
            raise ValueError("O consumer group é obrigatório.")

        if not topic.strip():
            raise ValueError("O tópico Kafka é obrigatório.")

        if poll_timeout_seconds <= 0:
            raise ValueError("O timeout de polling deve ser positivo.")

        self._topic = topic
        self._poll_timeout_seconds = poll_timeout_seconds
        self._handler: Callable[[dict[str, Any]], None] | None = None
        self._closed = False
        self._running = False
        self._stop_event = threading.Event()

        config: dict[str, Any] = {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "client.id": client_id,
            "auto.offset.reset": auto_offset_reset,
            "enable.auto.commit": enable_auto_commit,
            "enable.auto.offset.store": False,
        }

        if security_config:
            config.update(security_config)

        if additional_config:
            config.update(additional_config)

        # O offset será confirmado explicitamente após o processamento.
        config["enable.auto.commit"] = enable_auto_commit
        config["enable.auto.offset.store"] = False

        try:
            self._consumer = Consumer(config)
            self._consumer.subscribe([self._topic])
        except KafkaException as exc:
            raise PdfDiscoveredConsumerError(
                "Não foi possível inicializar o consumidor Kafka."
            ) from exc

    def registrar_handler(
        self,
        handler: Callable[[dict[str, Any]], None],
    ) -> None:
        if not callable(handler):
            raise ValueError("O handler informado deve ser executável.")

        self._handler = handler

    def consumir(self) -> None:
        if self._closed:
            raise PdfDiscoveredConsumerError(
                "O consumidor já foi encerrado."
            )

        if self._handler is None:
            raise PdfDiscoveredConsumerError(
                "Nenhum handler foi registrado para processar os eventos."
            )

        if self._running:
            raise PdfDiscoveredConsumerError(
                "O consumidor já está em execução."
            )

        self._running = True
        self._stop_event.clear()

        try:
            while not self._stop_event.is_set():
                message = self._consumer.poll(
                    self._poll_timeout_seconds
                )

                if message is None:
                    continue

                if message.error():
                    self._tratar_erro_kafka(message)
                    continue

                self._processar_mensagem(message)

        except KafkaException as exc:
            raise PdfDiscoveredConsumerError(
                "Falha durante o consumo de mensagens Kafka."
            ) from exc
        finally:
            self._running = False

    def consumir_mensagem(self, message: Message) -> None:
        if message.error():
            self._tratar_erro_kafka(message)
            return

        self._processar_mensagem(message)

    def _processar_mensagem(self, message: Message) -> None:
        try:
            payload = self._decodificar_mensagem(message)
            self._validar_evento(payload)

            if self._handler is None:
                raise PdfDiscoveredConsumerError(
                    "Nenhum handler foi registrado."
                )

            self._handler(payload)

            self._confirmar_offset(message)

            logger.info(
                "Evento de PDF processado. event_id=%s topic=%s partition=%s offset=%s",
                payload["event_id"],
                message.topic(),
                message.partition(),
                message.offset(),
            )

        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.exception(
                "Evento inválido recebido. topic=%s partition=%s offset=%s",
                message.topic(),
                message.partition(),
                message.offset(),
            )
            raise PdfDiscoveredConsumerError(
                "A mensagem recebida não contém um evento válido."
            ) from exc

        except Exception:
            logger.exception(
                "Falha ao processar evento. topic=%s partition=%s offset=%s",
                message.topic(),
                message.partition(),
                message.offset(),
            )
            raise

    @staticmethod
    def _decodificar_mensagem(message: Message) -> dict[str, Any]:
        raw_value = message.value()

        if not raw_value:
            raise ValueError("A mensagem Kafka está vazia.")

        payload = json.loads(raw_value.decode("utf-8"))

        if not isinstance(payload, dict):
            raise ValueError("O evento precisa ser um objeto JSON.")

        return payload

    def _validar_evento(self, payload: dict[str, Any]) -> None:
        required_fields = {
            "event_id",
            "storage_key",
            "checksum",
            "size_bytes",
            "file_name",
            "content_type",
            "metadata",
            "discovered_at",
            "schema_version",
        }

        missing_fields = required_fields.difference(payload)

        if missing_fields:
            raise ValueError(
                f"Campos obrigatórios ausentes: {', '.join(sorted(missing_fields))}"
            )

        if not isinstance(payload["metadata"], dict):
            raise ValueError("O campo metadata precisa ser um objeto.")

        metadata = payload["metadata"]

        metadata_fields = {
            "source_id",
            "source_name",
            "course_code",
            "course_name",
            "edition_year",
            "document_type",
            "source_url",
        }

        missing_metadata = metadata_fields.difference(metadata)

        if missing_metadata:
            raise ValueError(
                "Metadados incompletos: "
                + ", ".join(sorted(missing_metadata))
            )

        if payload["content_type"] != "application/pdf":
            raise ValueError("O evento não representa um arquivo PDF.")

        if not isinstance(payload["size_bytes"], int) or isinstance(
            payload["size_bytes"], bool
        ):
            raise ValueError("O tamanho do PDF precisa ser um número inteiro.")

        if payload["size_bytes"] <= 0:
            raise ValueError("O tamanho do PDF precisa ser positivo.")

        if not isinstance(payload["checksum"], str):
            raise ValueError("O checksum precisa ser uma string.")

        checksum = payload["checksum"]

        if (
            len(checksum) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in checksum)
        ):
            raise ValueError("O checksum SHA-256 é inválido.")

        if not isinstance(payload["storage_key"], str) or not payload["storage_key"].strip():
            raise ValueError("O storage_key é obrigatório.")

        if not isinstance(payload["file_name"], str) or not payload["file_name"].lower().endswith(".pdf"):
            raise ValueError("O nome do arquivo precisa identificar um PDF.")

        if payload.get("event_type", self.EVENT_TYPE) != self.EVENT_TYPE:
            raise ValueError("Tipo de evento incompatível.")

    def _confirmar_offset(self, message: Message) -> None:
        try:
            self._consumer.commit(
                message=message,
                asynchronous=False,
            )
        except KafkaException as exc:
            raise PdfDiscoveredConsumerError(
                "Não foi possível confirmar o offset da mensagem."
            ) from exc

    @staticmethod
    def _tratar_erro_kafka(message: Message) -> None:
        error = message.error()

        if error.code() == KafkaError._PARTITION_EOF:
            logger.debug(
                "Fim da partição Kafka: %s",
                message.partition(),
            )
            return

        raise PdfDiscoveredConsumerError(
            f"Erro retornado pelo Kafka: {error}"
        )

    def solicitar_parada(self) -> None:
        self._stop_event.set()

    def instalar_sinais_de_encerramento(self) -> None:
        signal.signal(signal.SIGTERM, self._sinalizar_parada)
        signal.signal(signal.SIGINT, self._sinalizar_parada)

    def _sinalizar_parada(
        self,
        signum: int,
        frame: Any,
    ) -> None:
        logger.info(
            "Sinal de encerramento recebido: %s",
            signum,
        )
        self.solicitar_parada()

    def fechar(self) -> None:
        if self._closed:
            return

        self.solicitar_parada()

        try:
            self._consumer.close()
        except KafkaException as exc:
            raise PdfDiscoveredConsumerError(
                "Falha ao encerrar o consumidor Kafka."
            ) from exc
        finally:
            self._closed = True

    def __enter__(self) -> PdfDiscoveredConsumer:
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        self.fechar()
