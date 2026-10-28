from __future__ import annotations

import logging
import traceback

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from extraction.producers.extraction_error_producer import (
    ExtractionErrorProducer,
    ExtractionErrorProducerError,
    ExtractionErrorPublicationError,
)
from extraction.resilience.retry_policy import (
    RetryExhaustedError,
)


logger = logging.getLogger(__name__)


class DeadLetterError(Exception):
    """Erro durante o encaminhamento de mensagens para a DLQ"""


class DeadLetterPublicationError(DeadLetterError):
    """Não foi possível confirmar a publicação na DLQ"""


@dataclass(frozen=True)
class DeadLetterResult:
    original_event_id: str
    dead_letter_event_id: str
    storage_key: str
    attempt: int
    published: bool


class DeadLetterHandler:
    """Coordena o encaminhamento de falhas para a DLQ"""

    def __init__(
        self,
        producer: ExtractionErrorProducer,
        max_processing_attempts: int = 3,
    ) -> None:
        if max_processing_attempts < 1:
            raise ValueError(
                "O número máximo de tentativas deve ser positivo"
            )

        self.producer = producer
        self.max_processing_attempts = max_processing_attempts

    def processar_com_fallback(
        self,
        handler: Callable[..., Any],
        event: Mapping[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> bool:

        event_id = self._extract_event_id(event)
        storage_key = self._extract_storage_key(event)

        for attempt in range(1, self.max_processing_attempts + 1):
            try:
                handler(event, *args, **kwargs)

                logger.debug(
                    "Evento %s processado com sucesso.",
                    event_id,
                )

                return True

            except Exception as error:
                if attempt < self.max_processing_attempts:
                    logger.warning(
                        "Falha no processamento do evento %s "
                        "(tentativa %s/%s): %s",
                        event_id,
                        attempt,
                        self.max_processing_attempts,
                        type(error).__name__,
                    )

                    continue

                return self._encaminhar_para_dlq(
                    event_id=event_id,
                    storage_key=storage_key,
                    error=error,
                    attempt=attempt,
                    metadata=event.get("metadata", {}),
                )

        return False

    def encaminhar(
        self,
        event: Mapping[str, Any],
        error: Exception,
        attempt: int,
        retryable: bool = False,
    ) -> DeadLetterResult:

        event_id = self._extract_event_id(event)
        storage_key = self._extract_storage_key(event)

        return self._publicar(
            event_id=event_id,
            storage_key=storage_key,
            error=error,
            attempt=attempt,
            retryable=retryable,
            metadata=event.get("metadata", {}),
        )

    def _encaminhar_para_dlq(
        self,
        event_id: str,
        storage_key: str,
        error: Exception,
        attempt: int,
        metadata: Any,
    ) -> bool:
        try:
            result = self._publicar(
                event_id=event_id,
                storage_key=storage_key,
                error=error,
                attempt=attempt,
                retryable=False,
                metadata=metadata,
            )

            logger.error(
                "Evento %s encaminhado para a DLQ com identificador %s.",
                event_id,
                result.dead_letter_event_id,
            )

            return True

        except DeadLetterPublicationError:
            logger.exception(
                "Não foi possível encaminhar o evento %s para a DLQ. "
                "O offset original não deve ser confirmado.",
                event_id,
            )

            return False

    def _publicar(
        self,
        event_id: str,
        storage_key: str,
        error: Exception,
        attempt: int,
        retryable: bool,
        metadata: Any,
    ) -> DeadLetterResult:
        stack_trace = "".join(
            traceback.format_exception(
                type(error),
                error,
                error.__traceback__,
            )
        )

        try:
            result = self.producer.publicar_e_aguardar(
                original_event_id=event_id,
                storage_key=storage_key,
                error=error,
                attempt=attempt,
                retryable=retryable,
                stack_trace=stack_trace,
                metadata=(
                    metadata if isinstance(metadata, Mapping) else {}
                ),
            )

        except (
            ExtractionErrorProducerError,
            ExtractionErrorPublicationError,
        ) as publication_error:
            raise DeadLetterPublicationError(
                f"Falha ao publicar evento {event_id} na DLQ."
            ) from publication_error

        except Exception as publication_error:
            raise DeadLetterPublicationError(
                f"Erro inesperado ao publicar evento {event_id} na DLQ."
            ) from publication_error

        return DeadLetterResult(
            original_event_id=event_id,
            dead_letter_event_id=result.event_id,
            storage_key=storage_key,
            attempt=attempt,
            published=True,
        )

    @staticmethod
    def _extract_event_id(event: Mapping[str, Any]) -> str:
        event_id = event.get("event_id")

        if not isinstance(event_id, str) or not event_id.strip():
            raise DeadLetterError(
                "O evento original não possui um event_id válido."
            )

        return event_id

    @staticmethod
    def _extract_storage_key(event: Mapping[str, Any]) -> str:
        storage_key = event.get("storage_key")

        if not isinstance(storage_key, str) or not storage_key.strip():
            raise DeadLetterError(
                "O evento original não possui um storage_key válido."
            )

        return storage_key
