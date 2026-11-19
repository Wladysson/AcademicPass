from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from threading import RLock
from typing import BinaryIO
from uuid import uuid4

from ingestion.storage.pdf_storage import (
    PdfNotFoundError,
    PdfStorage,
    PdfStorageError,
    PdfStorageIntegrityError,
    PdfStorageMetadata,
)

logger = logging.getLogger(__name__)


class LocalVolumePdfStorage(PdfStorage):

    METADATA_SUFFIX = ".metadata.json"
    PDF_SIGNATURE = b"%PDF-"

    def __init__(
        self,
        storage_path: str,
        max_file_size_mb: int = 50,
    ) -> None:
        if not storage_path or not storage_path.strip():
            raise ValueError("O diretório de armazenamento é obrigatório.")

        if max_file_size_mb <= 0:
            raise ValueError("O tamanho máximo deve ser positivo.")

        self.storage_path = Path(storage_path).expanduser().resolve()
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self._lock = RLock()

        try:
            self.storage_path.mkdir(
                parents=True,
                exist_ok=True,
            )

            if not self.storage_path.is_dir():
                raise PdfStorageError(
                    "O caminho configurado não é um diretório."
                )

            if not os.access(self.storage_path, os.W_OK):
                raise PdfStorageError(
                    "O diretório de armazenamento não possui permissão de escrita."
                )

        except OSError as exc:
            raise PdfStorageError(
                "Não foi possível inicializar o volume de armazenamento."
            ) from exc

        logger.info(
            "Armazenamento local inicializado: path=%s",
            self.storage_path,
        )

    def salvar(
        self,
        file_name: str,
        content: bytes | BinaryIO,
        checksum: str,
    ) -> PdfStorageMetadata:
        safe_file_name = self._validar_nome_arquivo(file_name)
        self._validar_checksum(checksum)

        pdf_content = self._ler_conteudo(content)

        if not pdf_content.startswith(self.PDF_SIGNATURE):
            raise PdfStorageIntegrityError(
                "O conteúdo informado não possui uma assinatura PDF válida."
            )

        calculated_checksum = hashlib.sha256(pdf_content).hexdigest()

        if calculated_checksum != checksum.lower():
            raise PdfStorageIntegrityError(
                "O checksum informado não corresponde ao conteúdo do PDF."
            )

        if len(pdf_content) > self.max_file_size_bytes:
            raise PdfStorageError(
                "O documento excede o tamanho máximo permitido."
            )

        storage_key = f"{uuid4().hex}/{safe_file_name}"
        file_path = self._resolver_caminho(storage_key)
        metadata_path = self._resolver_caminho(
            f"{storage_key}{self.METADATA_SUFFIX}"
        )

        created_at = datetime.now(timezone.utc)

        metadata = PdfStorageMetadata(
            storage_key=storage_key,
            file_name=safe_file_name,
            checksum=calculated_checksum,
            size_bytes=len(pdf_content),
            content_type="application/pdf",
            created_at=created_at,
        )

        metadata_content = self._serializar_metadados(metadata)

        with self._lock:
            try:
                file_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                self._gravar_atomicamente(
                    destination=file_path,
                    content=pdf_content,
                )

                self._gravar_atomicamente(
                    destination=metadata_path,
                    content=metadata_content,
                )

                logger.info(
                    "PDF armazenado no volume local: key=%s, size=%d",
                    storage_key,
                    len(pdf_content),
                )

                return metadata

            except Exception as exc:
                self._remover_se_existir(file_path)
                self._remover_se_existir(metadata_path)

                if isinstance(exc, PdfStorageError):
                    raise

                logger.exception(
                    "Falha ao armazenar PDF no volume local: key=%s",
                    storage_key,
                )

                raise PdfStorageError(
                    "Não foi possível armazenar o documento no volume local."
                ) from exc

    def recuperar(self, storage_key: str) -> bytes:
        file_path = self._resolver_caminho(storage_key)

        with self._lock:
            if not file_path.is_file():
                raise PdfNotFoundError(
                    f"Documento não encontrado: {storage_key}"
                )

            try:
                metadata = self.obter_metadados(storage_key)

                with file_path.open("rb") as file:
                    content = file.read(self.max_file_size_bytes + 1)

                if len(content) > self.max_file_size_bytes:
                    raise PdfStorageIntegrityError(
                        "O documento recuperado excede o tamanho máximo permitido."
                    )

                if not content.startswith(self.PDF_SIGNATURE):
                    raise PdfStorageIntegrityError(
                        "O documento recuperado não possui uma assinatura PDF válida."
                    )

                calculated_checksum = hashlib.sha256(content).hexdigest()

                if calculated_checksum != metadata.checksum:
                    raise PdfStorageIntegrityError(
                        "O checksum do documento recuperado não corresponde "
                        "ao checksum registrado."
                    )

                if len(content) != metadata.size_bytes:
                    raise PdfStorageIntegrityError(
                        "O tamanho do documento recuperado não corresponde "
                        "aos metadados registrados."
                    )

                return content

            except (PdfNotFoundError, PdfStorageIntegrityError):
                raise

            except OSError as exc:
                logger.exception(
                    "Falha ao recuperar PDF do volume local: key=%s",
                    storage_key,
                )

                raise PdfStorageError(
                    "Não foi possível recuperar o documento do volume local."
                ) from exc

    def obter_metadados(
        self,
        storage_key: str,
    ) -> PdfStorageMetadata:
        metadata_path = self._resolver_caminho(
            f"{storage_key}{self.METADATA_SUFFIX}"
        )

        if not metadata_path.is_file():
            raise PdfNotFoundError(
                f"Metadados não encontrados para o documento: {storage_key}"
            )

        try:
            with metadata_path.open("r", encoding="utf-8") as file:
                data = json.load(file)

            return PdfStorageMetadata(
                storage_key=data["storage_key"],
                file_name=data["file_name"],
                checksum=data["checksum"],
                size_bytes=data["size_bytes"],
                content_type=data["content_type"],
                created_at=datetime.fromisoformat(data["created_at"]),
            )

        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise PdfStorageIntegrityError(
                "Os metadados do documento estão inválidos ou corrompidos."
            ) from exc

        except OSError as exc:
            raise PdfStorageError(
                "Não foi possível ler os metadados do documento."
            ) from exc

    def excluir(self, storage_key: str) -> None:
        file_path = self._resolver_caminho(storage_key)
        metadata_path = self._resolver_caminho(
            f"{storage_key}{self.METADATA_SUFFIX}"
        )

        with self._lock:
            if not file_path.is_file():
                raise PdfNotFoundError(
                    f"Documento não encontrado: {storage_key}"
                )

            try:
                file_path.unlink()

                if metadata_path.is_file():
                    metadata_path.unlink()

                self._remover_diretorios_vazios(file_path.parent)

                logger.info(
                    "PDF removido do volume local: key=%s",
                    storage_key,
                )

            except OSError as exc:
                raise PdfStorageError(
                    "Não foi possível excluir o documento do volume local."
                ) from exc

    def existe(self, storage_key: str) -> bool:
        file_path = self._resolver_caminho(storage_key)
        return file_path.is_file()

    def _resolver_caminho(self, storage_key: str) -> Path:
        if not storage_key or not storage_key.strip():
            raise ValueError("O storage_key é obrigatório.")

        if "\\" in storage_key or storage_key.startswith("/"):
            raise ValueError("O storage_key informado é inválido.")

        relative_path = PurePosixPath(storage_key)

        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
            or not relative_path.parts
        ):
            raise ValueError("O storage_key informado é inválido.")

        resolved_path = (
            self.storage_path / Path(*relative_path.parts)
        ).resolve()

        try:
            resolved_path.relative_to(self.storage_path)
        except ValueError as exc:
            raise ValueError(
                "O caminho solicitado está fora do diretório autorizado."
            ) from exc

        return resolved_path

    def _gravar_atomicamente(
        self,
        destination: Path,
        content: bytes,
    ) -> None:
        temporary_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=destination.parent,
                prefix=".academicpass-",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)

                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            os.replace(temporary_path, destination)

        finally:
            if temporary_path is not None:
                self._remover_se_existir(temporary_path)

    def _ler_conteudo(self, content: bytes | BinaryIO) -> bytes:
        if isinstance(content, bytes):
            if len(content) > self.max_file_size_bytes:
                raise PdfStorageError(
                    "O documento excede o tamanho máximo permitido."
                )

            return content

        if not hasattr(content, "read"):
            raise TypeError(
                "O conteúdo deve ser bytes ou um stream binário."
            )

        result = bytearray()

        while True:
            remaining = self.max_file_size_bytes + 1 - len(result)

            if remaining <= 0:
                break

            chunk = content.read(min(64 * 1024, remaining))

            if not chunk:
                break

            if not isinstance(chunk, bytes):
                raise TypeError(
                    "O stream deve retornar conteúdo binário."
                )

            result.extend(chunk)

        if len(result) > self.max_file_size_bytes:
            raise PdfStorageError(
                "O documento excede o tamanho máximo permitido."
            )

        return bytes(result)

    @staticmethod
    def _serializar_metadados(
        metadata: PdfStorageMetadata,
    ) -> bytes:
        data = {
            "storage_key": metadata.storage_key,
            "file_name": metadata.file_name,
            "checksum": metadata.checksum,
            "size_bytes": metadata.size_bytes,
            "content_type": metadata.content_type,
            "created_at": metadata.created_at.isoformat(),
        }

        return json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

    @staticmethod
    def _validar_nome_arquivo(file_name: str) -> str:
        if not file_name or not file_name.strip():
            raise ValueError("O nome do arquivo é obrigatório.")

        if "/" in file_name or "\\" in file_name:
            raise ValueError(
                "O nome do arquivo não pode conter separadores."
            )

        safe_name = re.sub(
            r"[^a-zA-Z0-9._-]",
            "_",
            file_name.strip(),
        )

        if not safe_name.lower().endswith(".pdf"):
            raise ValueError("O arquivo precisa possuir extensão .pdf.")

        if safe_name in {".pdf", "..pdf"}:
            raise ValueError("O nome do arquivo é inválido.")

        return safe_name

    @staticmethod
    def _validar_checksum(checksum: str) -> None:
        if not isinstance(checksum, str) or len(checksum) != 64:
            raise ValueError(
                "O checksum SHA-256 deve possuir 64 caracteres."
            )

        try:
            int(checksum, 16)
        except ValueError as exc:
            raise ValueError(
                "O checksum informado não é um hexadecimal válido."
            ) from exc

    @staticmethod
    def _remover_se_existir(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning(
                "Não foi possível remover arquivo temporário: %s",
                path,
            )

    def _remover_diretorios_vazios(self, directory: Path) -> None:
        current = directory

        while current != self.storage_path:
            try:
                current.rmdir()
                current = current.parent
            except OSError:
                break
