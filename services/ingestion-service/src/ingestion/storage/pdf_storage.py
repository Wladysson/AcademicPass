from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO


class PdfStorageError(Exception):
    """Erro relacionado ao armazenamento de documentos PDF"""


class PdfNotFoundError(PdfStorageError):
    """Documento PDF não encontrado no armazenamento"""


class PdfStorageIntegrityError(PdfStorageError):
    """Falha na integridade do documento armazenado"""


@dataclass(frozen=True, slots=True)
class PdfStorageMetadata:
    storage_key: str
    file_name: str
    checksum: str
    size_bytes: int
    content_type: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.storage_key or not self.storage_key.strip():
            raise ValueError("O storage_key é obrigatório.")

        if not self.file_name or not self.file_name.strip():
            raise ValueError("O nome do arquivo é obrigatório.")

        if not self.file_name.lower().endswith(".pdf"):
            raise ValueError("Somente arquivos PDF são permitidos.")

        if len(self.checksum) != 64:
            raise ValueError("O checksum SHA-256 deve possuir 64 caracteres.")

        try:
            int(self.checksum, 16)
        except ValueError as exc:
            raise ValueError(
                "O checksum informado não é um SHA-256 hexadecimal válido."
            ) from exc

        if self.size_bytes <= 0:
            raise ValueError("O tamanho do documento deve ser positivo.")

        if self.content_type != "application/pdf":
            raise ValueError("O content type deve ser application/pdf.")

        if self.created_at.tzinfo is None:
            raise ValueError("A data de criação deve possuir fuso horário.")


class PdfStorage(ABC):

    @abstractmethod
    def salvar(
        self,
        file_name: str,
        content: bytes | BinaryIO,
        checksum: str,
    ) -> PdfStorageMetadata:

        raise NotImplementedError

    @abstractmethod
    def recuperar(
        self,
        storage_key: str,
    ) -> bytes:

        raise NotImplementedError

    @abstractmethod
    def obter_metadados(
        self,
        storage_key: str,
    ) -> PdfStorageMetadata:

        raise NotImplementedError

    @abstractmethod
    def excluir(
        self,
        storage_key: str,
    ) -> None:

        raise NotImplementedError

    @abstractmethod
    def existe(
        self,
        storage_key: str,
    ) -> bool:

        raise NotImplementedError
