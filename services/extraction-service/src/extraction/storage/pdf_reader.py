from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import BinaryIO


class PdfReaderError(Exception):
    """Erro relacionado à leitura de documentos PDF"""


class PdfNotFoundError(PdfReaderError):
    """Documento PDF não encontrado no storage"""


class PdfIntegrityError(PdfReaderError):
    """Documento PDF com integridade comprometida"""


@dataclass(frozen=True, slots=True)
class PdfDocument:
    storage_key: str
    file_name: str
    content: bytes
    checksum: str
    size_bytes: int
    content_type: str
    retrieved_at: datetime

    def __post_init__(self) -> None:
        if not self.storage_key.strip():
            raise ValueError("O storage_key é obrigatório.")

        if not self.file_name.strip():
            raise ValueError("O nome do arquivo é obrigatório.")

        if not self.file_name.lower().endswith(".pdf"):
            raise ValueError("O arquivo precisa possuir extensão PDF.")

        if not isinstance(self.content, bytes) or not self.content:
            raise ValueError("O conteúdo do PDF é obrigatório.")

        if self.size_bytes <= 0 or self.size_bytes != len(self.content):
            raise ValueError("O tamanho informado não corresponde ao conteúdo.")

        if self.content_type != "application/pdf":
            raise ValueError("O content_type precisa ser application/pdf.")

        if not re.fullmatch(r"[a-fA-F0-9]{64}", self.checksum):
            raise ValueError("O checksum precisa ser um SHA-256 válido.")

        if self.content[:5] != b"%PDF-":
            raise ValueError("O conteúdo informado não possui assinatura PDF.")

        actual_checksum = hashlib.sha256(self.content).hexdigest()

        if actual_checksum.lower() != self.checksum.lower():
            raise ValueError("O checksum não corresponde ao conteúdo do PDF.")

        if (
            self.retrieved_at.tzinfo is None
            or self.retrieved_at.utcoffset() is None
        ):
            raise ValueError("A data de recuperação precisa possuir fuso horário.")


class PdfReader(ABC):

    @abstractmethod
    def recuperar(
        self,
        storage_key: str,
        checksum: str,
    ) -> PdfDocument:

        raise NotImplementedError

    @abstractmethod
    def existe(self, storage_key: str) -> bool:
        """Verifica se um documento existe no storage."""
        raise NotImplementedError

    @abstractmethod
    def obter_metadados(self, storage_key: str) -> dict[str, str | int | None]:
        """Recupera os metadados associados ao documento."""
        raise NotImplementedError

    @staticmethod
    def validar_storage_key(storage_key: str) -> None:
        if not isinstance(storage_key, str) or not storage_key.strip():
            raise ValueError("O storage_key é obrigatório.")

        normalized_key = storage_key.replace("\\", "/")

        if normalized_key.startswith("/"):
            raise ValueError("O storage_key não pode ser um caminho absoluto.")

        if any(part in {".", ".."} for part in normalized_key.split("/")):
            raise ValueError("O storage_key contém segmentos inválidos.")

        if "\x00" in storage_key:
            raise ValueError("O storage_key contém caracteres inválidos.")

    @staticmethod
    def validar_checksum(checksum: str) -> None:
        if not isinstance(checksum, str) or not re.fullmatch(
            r"[a-fA-F0-9]{64}",
            checksum,
        ):
            raise ValueError("O checksum informado precisa ser um SHA-256 válido.")

    @staticmethod
    def criar_documento(
        storage_key: str,
        file_name: str,
        content: bytes | BinaryIO,
        checksum: str,
        content_type: str,
    ) -> PdfDocument:

        PdfReader.validar_storage_key(storage_key)
        PdfReader.validar_checksum(checksum)

        if hasattr(content, "read"):
            content = content.read()

        if not isinstance(content, bytes) or not content:
            raise PdfIntegrityError("O conteúdo recuperado está vazio.")

        if content_type != "application/pdf":
            raise PdfIntegrityError("O documento não é identificado como PDF.")

        if not content.startswith(b"%PDF-"):
            raise PdfIntegrityError("A assinatura do arquivo PDF é inválida.")

        actual_checksum = hashlib.sha256(content).hexdigest()

        if actual_checksum.lower() != checksum.lower():
            raise PdfIntegrityError(
                "O checksum do documento não corresponde ao esperado."
            )

        return PdfDocument(
            storage_key=storage_key,
            file_name=file_name,
            content=content,
            checksum=actual_checksum,
            size_bytes=len(content),
            content_type=content_type,
            retrieved_at=datetime.now(timezone.utc),
        )
