from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from extraction.storage.pdf_reader import (
    PdfDocument,
    PdfIntegrityError,
    PdfNotFoundError,
    PdfReader,
    PdfReaderError,
)

logger = logging.getLogger(__name__)


class LocalVolumePdfReader(PdfReader):

    METADATA_SUFFIX = ".metadata.json"

    def __init__(
        self,
        storage_path: str | Path,
        max_file_size_mb: int = 50,
    ) -> None:
        if max_file_size_mb <= 0:
            raise ValueError("O limite de tamanho precisa ser positivo.")

        self._storage_path = Path(storage_path).expanduser().resolve()
        self._max_file_size_bytes = max_file_size_mb * 1024 * 1024

        if not self._storage_path.exists():
            raise PdfReaderError(
                f"O diretório de armazenamento não existe: {self._storage_path}"
            )

        if not self._storage_path.is_dir():
            raise PdfReaderError(
                "O caminho de armazenamento informado não é um diretório."
            )

        if not self._storage_path.is_dir():
            raise PdfReaderError(
                "O caminho de armazenamento não é um diretório válido."
            )

        if not self._storage_path.exists():
            raise PdfReaderError(
                "O diretório de armazenamento não está disponível."
            )

        if not self._storage_path.stat().st_mode:
            raise PdfReaderError(
                "Não foi possível consultar as permissões do volume."
            )

    def recuperar(
        self,
        storage_key: str,
        checksum: str,
    ) -> PdfDocument:
        self.validar_storage_key(storage_key)
        self.validar_checksum(checksum)

        pdf_path = self._resolver_caminho(storage_key)

        if not pdf_path.is_file():
            raise PdfNotFoundError(
                f"Documento não encontrado no volume compartilhado: {storage_key}"
            )

        metadata_path = self._resolver_caminho(
            f"{storage_key}{self.METADATA_SUFFIX}"
        )

        try:
            metadata = self._ler_metadados(metadata_path)

            expected_checksum = metadata.get("checksum")

            if expected_checksum and expected_checksum.lower() != checksum.lower():
                raise PdfIntegrityError(
                    "O checksum informado diverge dos metadados do volume."
                )

            expected_size = metadata.get("size_bytes")

            if not isinstance(expected_size, int) or isinstance(expected_size, bool):
                raise PdfIntegrityError(
                    "Os metadados não possuem um tamanho válido."
                )

            if expected_size <= 0 or expected_size > self._max_file_size_bytes:
                raise PdfIntegrityError(
                    "O tamanho registrado do PDF é inválido ou excede o limite."
                )

            actual_size = pdf_path.stat().st_size

            if actual_size != expected_size:
                raise PdfIntegrityError(
                    "O tamanho do arquivo diverge dos metadados."
                )

            if actual_size > self._max_file_size_bytes:
                raise PdfIntegrityError(
                    "O documento excede o limite de leitura permitido."
                )

            with pdf_path.open("rb") as file:
                content = file.read(self._max_file_size_bytes + 1)

            if len(content) > self._max_file_size_bytes:
                raise PdfIntegrityError(
                    "O documento excede o limite de leitura permitido."
                )

            file_name = metadata.get("file_name")

            if not isinstance(file_name, str) or not file_name.strip():
                file_name = pdf_path.name

            content_type = metadata.get("content_type")

            if not isinstance(content_type, str):
                raise PdfIntegrityError(
                    "Os metadados não identificam o tipo do documento."
                )

            document = self.criar_documento(
                storage_key=storage_key,
                file_name=file_name,
                content=content,
                checksum=checksum,
                content_type=content_type,
            )

            logger.info(
                "PDF recuperado do volume compartilhado. "
                "storage_key=%s size_bytes=%s",
                storage_key,
                document.size_bytes,
            )

            return document

        except PdfIntegrityError:
            raise

        except FileNotFoundError as exc:
            raise PdfNotFoundError(
                f"Documento ou metadados não encontrados: {storage_key}"
            ) from exc

        except PermissionError as exc:
            raise PdfReaderError(
                "Permissão negada ao acessar o PDF no volume compartilhado."
            ) from exc

        except OSError as exc:
            raise PdfReaderError(
                "Falha de leitura no volume compartilhado."
            ) from exc

    def existe(self, storage_key: str) -> bool:
        self.validar_storage_key(storage_key)

        pdf_path = self._resolver_caminho(storage_key)

        try:
            return pdf_path.is_file()

        except OSError as exc:
            raise PdfReaderError(
                "Não foi possível verificar a existência do PDF."
            ) from exc

    def obter_metadados(
        self,
        storage_key: str,
    ) -> dict[str, str | int | None]:
        self.validar_storage_key(storage_key)

        pdf_path = self._resolver_caminho(storage_key)

        if not pdf_path.is_file():
            raise PdfNotFoundError(
                f"Documento não encontrado: {storage_key}"
            )

        metadata_path = self._resolver_caminho(
            f"{storage_key}{self.METADATA_SUFFIX}"
        )

        try:
            metadata = self._ler_metadados(metadata_path)

            return {
                "storage_key": storage_key,
                "file_name": metadata.get("file_name"),
                "checksum": metadata.get("checksum"),
                "size_bytes": metadata.get("size_bytes"),
                "content_type": metadata.get("content_type"),
                "created_at": metadata.get("created_at"),
            }

        except FileNotFoundError as exc:
            raise PdfNotFoundError(
                f"Metadados não encontrados para o documento: {storage_key}"
            ) from exc

        except PermissionError as exc:
            raise PdfReaderError(
                "Permissão negada ao consultar os metadados."
            ) from exc

        except OSError as exc:
            raise PdfReaderError(
                "Falha ao consultar os metadados do documento."
            ) from exc

    def _resolver_caminho(self, storage_key: str) -> Path:
        self.validar_storage_key(storage_key)

        candidate = (self._storage_path / storage_key).resolve()

        try:
            candidate.relative_to(self._storage_path)
        except ValueError as exc:
            raise ValueError(
                "O caminho solicitado está fora do volume compartilhado."
            ) from exc

        return candidate

    @staticmethod
    def _ler_metadados(metadata_path: Path) -> dict[str, Any]:
        try:
            with metadata_path.open("r", encoding="utf-8") as file:
                metadata = json.load(file)

        except json.JSONDecodeError as exc:
            raise PdfIntegrityError(
                "O arquivo de metadados contém JSON inválido."
            ) from exc

        if not isinstance(metadata, dict):
            raise PdfIntegrityError(
                "O conteúdo dos metadados precisa ser um objeto JSON."
            )

        return metadata
