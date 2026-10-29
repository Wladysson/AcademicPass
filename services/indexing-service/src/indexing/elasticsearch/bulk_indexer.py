from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk


logger = logging.getLogger(__name__)

DEFAULT_INDEX = "academicpass-questions"


class BulkIndexerError(Exception):
    """Erro durante a execução de uma operação de indexação em lote."""


class InvalidBulkDocumentError(BulkIndexerError):
    """Documento inválido para indexação."""


@dataclass(frozen=True, slots=True)
class BulkItemResult:
    """Resultado da indexação de um documento individual."""

    document_id: str
    successful: bool
    status: int | None = None
    operation: str = "index"
    error: str | None = None


@dataclass(frozen=True, slots=True)
class BulkIndexingResult:
    """Resultado consolidado de uma operação de indexação em lote."""

    total: int
    successful: int
    failed: int
    items: tuple[BulkItemResult, ...]

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0

        return self.successful / self.total

    @property
    def successful_ids(self) -> tuple[str, ...]:
        return tuple(
            item.document_id
            for item in self.items
            if item.successful
        )

    @property
    def failed_items(self) -> tuple[BulkItemResult, ...]:
        return tuple(
            item
            for item in self.items
            if not item.successful
        )


class BulkIndexer:
    """Executa operações de indexação em lote no Elasticsearch."""

    def __init__(
        self,
        client: Elasticsearch | Any,
        index_name: str = DEFAULT_INDEX,
        chunk_size: int = 500,
        max_chunk_bytes: int = 10 * 1024 * 1024,
        id_field: str = "question_id",
        request_timeout: float | None = None,
    ) -> None:
        if client is None:
            raise ValueError("O cliente Elasticsearch é obrigatório.")

        if not self._validar_nome_indice(index_name):
            raise ValueError(
                f"Nome de índice Elasticsearch inválido: {index_name!r}."
            )

        if chunk_size < 1:
            raise ValueError("chunk_size deve ser maior que zero.")

        if max_chunk_bytes < 1:
            raise ValueError("max_chunk_bytes deve ser maior que zero.")

        if not id_field.strip():
            raise ValueError("id_field não pode ser vazio.")

        if request_timeout is not None and request_timeout <= 0:
            raise ValueError("request_timeout deve ser maior que zero.")

        self._client = (
            client.obter_cliente()
            if hasattr(client, "obter_cliente")
            else client
        )

        self._index_name = index_name
        self._chunk_size = chunk_size
        self._max_chunk_bytes = max_chunk_bytes
        self._id_field = id_field
        self._request_timeout = request_timeout

    def indexar_lote(
        self,
        documents: Sequence[Mapping[str, Any]],
        index_name: str | None = None,
    ) -> BulkIndexingResult:
        """Indexa vários documentos e retorna o resultado por documento."""
        if not documents:
            return BulkIndexingResult(
                total=0,
                successful=0,
                failed=0,
                items=(),
            )

        target_index = index_name or self._index_name

        if not self._validar_nome_indice(target_index):
            raise ValueError(
                f"Nome de índice Elasticsearch inválido: {target_index!r}."
            )

        actions = [
            self._criar_action(document, target_index)
            for document in documents
        ]

        results: list[BulkItemResult] = []

        try:
            options: dict[str, Any] = {
                "chunk_size": self._chunk_size,
                "max_chunk_bytes": self._max_chunk_bytes,
                "raise_on_error": False,
                "raise_on_exception": True,
                "yield_ok": True,
                "max_retries": 0,
            }

            if self._request_timeout is not None:
                options["request_timeout"] = self._request_timeout

            for successful, response in streaming_bulk(
                self._client,
                actions,
                **options,
            ):
                operation, details = next(iter(response.items()))

                results.append(
                    self._criar_resultado(
                        successful=successful,
                        operation=operation,
                        details=details,
                    )
                )

        except Exception as exc:
            logger.exception(
                "Falha durante a operação de bulk no índice %s.",
                target_index,
            )

            raise BulkIndexerError(
                "Não foi possível concluir a operação de indexação em lote. "
                "Alguns documentos podem já ter sido indexados."
            ) from exc

        successful_count = sum(
            1 for result in results if result.successful
        )
        failed_count = len(results) - successful_count

        if len(results) != len(documents):
            raise BulkIndexerError(
                "A quantidade de resultados retornados pelo Elasticsearch "
                "não corresponde à quantidade de documentos enviados."
            )

        summary = BulkIndexingResult(
            total=len(documents),
            successful=successful_count,
            failed=failed_count,
            items=tuple(results),
        )

        logger.info(
            "Bulk concluído no índice %s: total=%s, sucesso=%s, falhas=%s.",
            target_index,
            summary.total,
            summary.successful,
            summary.failed,
        )

        return summary

    def indexar(
        self,
        document: Mapping[str, Any],
        index_name: str | None = None,
    ) -> BulkItemResult:
        """Indexa um único documento utilizando a mesma infraestrutura bulk."""
        result = self.indexar_lote(
            documents=[document],
            index_name=index_name,
        )

        return result.items[0]

    def _criar_action(
        self,
        document: Mapping[str, Any],
        index_name: str,
    ) -> dict[str, Any]:
        if not isinstance(document, Mapping):
            raise InvalidBulkDocumentError(
                "Cada documento precisa ser um objeto compatível com Mapping."
            )

        document_id = document.get(self._id_field)

        if not isinstance(document_id, str) or not document_id.strip():
            raise InvalidBulkDocumentError(
                f"O documento precisa conter um identificador textual "
                f"válido no campo {self._id_field!r}."
            )

        return {
            "_op_type": "index",
            "_index": index_name,
            "_id": document_id.strip(),
            "_source": dict(document),
        }

    @staticmethod
    def _criar_resultado(
        successful: bool,
        operation: str,
        details: Mapping[str, Any],
    ) -> BulkItemResult:
        document_id = details.get("_id")

        if not isinstance(document_id, str):
            document_id = "unknown"

        status = details.get("status")

        if not isinstance(status, int):
            status = None

        error = details.get("error")

        if isinstance(error, Mapping):
            error_message = str(
                error.get("reason")
                or error.get("type")
                or error
            )
        elif error is not None:
            error_message = str(error)
        else:
            error_message = None

        return BulkItemResult(
            document_id=document_id,
            successful=successful,
            status=status,
            operation=operation,
            error=error_message,
        )

    @staticmethod
    def _validar_nome_indice(index_name: str) -> bool:
        if not isinstance(index_name, str):
            return False

        if not index_name or len(index_name) > 255:
            return False

        if index_name != index_name.lower():
            return False

        if index_name in {".", ".."}:
            return False

        if index_name.startswith(("-", "_", "+")):
            return False

        return re.fullmatch(r"[a-z0-9._-]+", index_name) is not None
