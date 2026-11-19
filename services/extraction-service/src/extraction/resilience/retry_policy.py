from __future__ import annotations

import asyncio
import logging
import random
import time

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, TypeVar

import httpx

from extraction.media.llm_media_client import (
    GeminiAuthenticationError,
    GeminiMediaClientError,
    GeminiRateLimitError,
    GeminiResponseError,
)
from extraction.storage.pdf_reader import (
    PdfIntegrityError,
    PdfNotFoundError,
    PdfReaderError,
)


logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryStrategy(str, Enum):
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"


class RetryExhaustedError(Exception):
    """Todas as tentativas de execução foram esgotadas."""

    def __init__(
        self,
        operation: str,
        attempts: int,
        last_error: Exception,
    ) -> None:
        self.operation = operation
        self.attempts = attempts
        self.last_error = last_error

        super().__init__(
            f"Operação '{operation}' falhou após "
            f"{attempts} tentativa(s): {last_error}"
        )


class NonRetryableError(Exception):
    """Erro que não deve provocar uma nova tentativa"""

@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 3
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    multiplier: float = 2.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    jitter: bool = True
    jitter_factor: float = 0.2

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError(
                "O número máximo de tentativas deve ser positivo."
            )

        if self.initial_delay_seconds < 0:
            raise ValueError(
                "O intervalo inicial não pode ser negativo."
            )

        if self.max_delay_seconds < self.initial_delay_seconds:
            raise ValueError(
                "O intervalo máximo não pode ser menor que o inicial."
            )

        if self.multiplier < 1:
            raise ValueError(
                "O multiplicador deve ser igual ou superior a 1."
            )

        if not 0 <= self.jitter_factor <= 1:
            raise ValueError(
                "O fator de jitter deve estar entre 0 e 1."
            )


class RetryPolicy:

    DEFAULT_PDF_CONFIG = RetryConfig(
        max_attempts=3,
        initial_delay_seconds=1.0,
        max_delay_seconds=10.0,
        multiplier=2.0,
    )

    DEFAULT_LLM_CONFIG = RetryConfig(
        max_attempts=4,
        initial_delay_seconds=2.0,
        max_delay_seconds=30.0,
        multiplier=2.0,
    )

    def __init__(
        self,
        config: RetryConfig | None = None,
        retryable_exceptions: tuple[type[Exception], ...] | None = None,
    ) -> None:
        self.config = config or RetryConfig()

        self.retryable_exceptions = retryable_exceptions or (
            PdfReaderError,
            GeminiRateLimitError,
            GeminiMediaClientError,
            httpx.TimeoutException,
            httpx.NetworkError,
            TimeoutError,
            ConnectionError,
        )

    @classmethod
    def for_pdf(cls) -> RetryPolicy:

        return cls(
            config=cls.DEFAULT_PDF_CONFIG,
            retryable_exceptions=(
                PdfReaderError,
                httpx.TimeoutException,
                httpx.NetworkError,
                TimeoutError,
                ConnectionError,
            ),
        )

    @classmethod
    def for_llm(cls) -> RetryPolicy:

        return cls(
            config=cls.DEFAULT_LLM_CONFIG,
            retryable_exceptions=(
                GeminiRateLimitError,
                GeminiMediaClientError,
                httpx.TimeoutException,
                httpx.NetworkError,
                TimeoutError,
                ConnectionError,
            ),
        )

    def execute(
        self,
        operation: Callable[..., T],
        *args: Any,
        operation_name: str | None = None,
        **kwargs: Any,
    ) -> T:
        """Executa uma operação síncrona com política de retry"""

        name = operation_name or getattr(
            operation,
            "__name__",
            "operation",
        )

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return operation(*args, **kwargs)

            except Exception as error:
                if not self._should_retry(error):
                    raise

                if attempt >= self.config.max_attempts:
                    raise RetryExhaustedError(
                        operation=name,
                        attempts=attempt,
                        last_error=error,
                    ) from error

                delay = self.calculate_delay(attempt)

                logger.warning(
                    "Operação %s falhou na tentativa %s/%s. "
                    "Nova tentativa em %.2f segundos. Erro: %s",
                    name,
                    attempt,
                    self.config.max_attempts,
                    delay,
                    type(error).__name__,
                )

                time.sleep(delay)

        raise RuntimeError("Estado inesperado na política de retry.")

    async def execute_async(
        self,
        operation: Callable[..., Any],
        *args: Any,
        operation_name: str | None = None,
        **kwargs: Any,
    ) -> T:
        """Executa uma operação assíncrona com política de retry."""

        name = operation_name or getattr(
            operation,
            "__name__",
            "async_operation",
        )

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return await operation(*args, **kwargs)

            except Exception as error:
                if not self._should_retry(error):
                    raise

                if attempt >= self.config.max_attempts:
                    raise RetryExhaustedError(
                        operation=name,
                        attempts=attempt,
                        last_error=error,
                    ) from error

                delay = self.calculate_delay(attempt)

                logger.warning(
                    "Operação assíncrona %s falhou na tentativa "
                    "%s/%s. Nova tentativa em %.2f segundos. Erro: %s",
                    name,
                    attempt,
                    self.config.max_attempts,
                    delay,
                    type(error).__name__,
                )

                await asyncio.sleep(delay)

        raise RuntimeError("Estado inesperado na política de retry.")

    def calculate_delay(self, attempt: int) -> float:

        if attempt < 1:
            raise ValueError("A tentativa deve ser positiva.")

        if self.config.strategy == RetryStrategy.FIXED:
            delay = self.config.initial_delay_seconds

        elif self.config.strategy == RetryStrategy.LINEAR:
            delay = (
                self.config.initial_delay_seconds * attempt
            )

        else:
            delay = (
                self.config.initial_delay_seconds
                * self.config.multiplier ** (attempt - 1)
            )

        delay = min(delay, self.config.max_delay_seconds)

        if self.config.jitter and delay > 0:
            variation = delay * self.config.jitter_factor

            delay = random.uniform(
                max(0.0, delay - variation),
                delay + variation,
            )

        return min(delay, self.config.max_delay_seconds)

    def _should_retry(self, error: Exception) -> bool:
        """Determina se uma falha permite nova tentativa."""

        if isinstance(error, NonRetryableError):
            return False

        if isinstance(
            error,
            (
                GeminiAuthenticationError,
                GeminiResponseError,
                PdfNotFoundError,
                PdfIntegrityError,
            ),
        ):
            return False

        return isinstance(
            error,
            self.retryable_exceptions,
        )
