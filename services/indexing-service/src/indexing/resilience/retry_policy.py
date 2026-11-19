from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, TypeVar

from elasticsearch import ApiError
from elastic_transport import ConnectionError, ConnectionTimeout


T = TypeVar("T")

logger = logging.getLogger(__name__)


class RetryStrategy(str, Enum):
    """Estratégias de cálculo do intervalo entre tentativas."""

    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


class RetryPolicyError(Exception):
    """Erro base da política de retentativas."""


class NonRetryableError(RetryPolicyError):
    """Indica que a operação falhou por um motivo não recuperável."""


class RetryExhaustedError(RetryPolicyError):
    """Indica que todas as tentativas disponíveis foram utilizadas."""

    def __init__(
        self,
        operation: str,
        attempts: int,
        last_exception: Exception,
    ) -> None:
        self.operation = operation
        self.attempts = attempts
        self.last_exception = last_exception

        super().__init__(
            f"A operação '{operation}' falhou após "
            f"{attempts} tentativa(s): {last_exception}"
        )


@dataclass(frozen=True, slots=True)
class RetryConfig:
    """Parâmetros de configuração das retentativas."""

    max_attempts: int = 3
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    multiplier: float = 2.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    jitter: bool = True
    jitter_factor: float = 0.2
    retryable_status_codes: frozenset[int] = frozenset(
        {408, 429, 500, 502, 503, 504}
    )

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts deve ser maior ou igual a 1.")

        if self.initial_delay_seconds < 0:
            raise ValueError(
                "initial_delay_seconds não pode ser negativo."
            )

        if self.max_delay_seconds < 0:
            raise ValueError(
                "max_delay_seconds não pode ser negativo."
            )

        if self.multiplier < 1:
            raise ValueError("multiplier deve ser maior ou igual a 1.")

        if not 0 <= self.jitter_factor <= 1:
            raise ValueError("jitter_factor deve estar entre 0 e 1.")

        if not isinstance(self.strategy, RetryStrategy):
            raise ValueError("Estratégia de retentativa inválida.")

        if any(
            not isinstance(status, int) or status < 100 or status > 599
            for status in self.retryable_status_codes
        ):
            raise ValueError("Código HTTP inválido na lista de retentativas.")


class RetryPolicy:
    """Executa operações com retentativas para falhas transitórias."""

    def __init__(
        self,
        config: RetryConfig | None = None,
        *,
        retryable_exceptions: tuple[type[Exception], ...] = (),
    ) -> None:
        self.config = config or RetryConfig()
        self.retryable_exceptions = retryable_exceptions

    @classmethod
    def for_elasticsearch(
        cls,
        max_attempts: int = 3,
        initial_delay_seconds: float = 1.0,
        max_delay_seconds: float = 30.0,
    ) -> RetryPolicy:
        """Cria uma política padrão para operações do Elasticsearch."""

        return cls(
            config=RetryConfig(
                max_attempts=max_attempts,
                initial_delay_seconds=initial_delay_seconds,
                max_delay_seconds=max_delay_seconds,
                multiplier=2.0,
                strategy=RetryStrategy.EXPONENTIAL,
                jitter=True,
                jitter_factor=0.2,
            )
        )

    def execute(
        self,
        operation: Callable[[], T],
        *,
        operation_name: str = "elasticsearch_operation",
    ) -> T:
        """Executa uma operação aplicando retentativas quando necessário."""

        last_exception: Exception | None = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return operation()

            except Exception as error:
                last_exception = error

                if not self._should_retry(error):
                    logger.error(
                        "Operação '%s' falhou com erro não recuperável: %s",
                        operation_name,
                        error,
                    )
                    raise NonRetryableError(
                        f"A operação '{operation_name}' não pode ser "
                        f"repetida: {error}"
                    ) from error

                if attempt >= self.config.max_attempts:
                    break

                delay = self._calculate_delay(attempt)

                logger.warning(
                    "Falha temporária na operação '%s'. "
                    "Tentativa %s/%s. Nova tentativa em %.2f segundos. "
                    "Erro: %s",
                    operation_name,
                    attempt,
                    self.config.max_attempts,
                    delay,
                    error,
                )

                time.sleep(delay)

        if last_exception is None:
            raise RetryPolicyError(
                f"A operação '{operation_name}' não foi executada."
            )

        logger.error(
            "Operação '%s' esgotou as retentativas disponíveis.",
            operation_name,
        )

        raise RetryExhaustedError(
            operation=operation_name,
            attempts=self.config.max_attempts,
            last_exception=last_exception,
        ) from last_exception

    def _should_retry(self, error: Exception) -> bool:
        """Determina se a falha permite uma nova tentativa."""

        if isinstance(error, (ConnectionError, ConnectionTimeout)):
            return True

        if isinstance(error, ApiError):
            status_code = getattr(error, "status_code", None)

            if status_code is None:
                return False

            return status_code in self.config.retryable_status_codes

        if self.retryable_exceptions and isinstance(
            error,
            self.retryable_exceptions,
        ):
            return True

        return False

    def _calculate_delay(self, attempt: int) -> float:
        """Calcula o intervalo de espera antes da próxima tentativa."""

        initial_delay = self.config.initial_delay_seconds

        if self.config.strategy == RetryStrategy.FIXED:
            delay = initial_delay

        elif self.config.strategy == RetryStrategy.LINEAR:
            delay = initial_delay * attempt

        else:
            delay = initial_delay * (
                self.config.multiplier ** (attempt - 1)
            )

        delay = min(delay, self.config.max_delay_seconds)

        if self.config.jitter and delay > 0:
            variation = delay * self.config.jitter_factor
            delay = random.uniform(
                max(0.0, delay - variation),
                delay + variation,
            )

        return min(delay, self.config.max_delay_seconds)
