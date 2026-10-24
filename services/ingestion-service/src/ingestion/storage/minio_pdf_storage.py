from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import PurePosixPath
from typing import BinaryIO
from uuid import uuid4

from minio import Minio
from minio.error import S3Error

from ingestion.storage.pdf_storage import (
    PdfNotFoundError,
    PdfStorage,
    PdfStorageError,
    PdfStorageIntegrityError,
    PdfStorageMetadata,
)

logger = logging.getLogger(__name__)


class MinioPdfStorage(PdfStorage):
    """Implementação de PdfStorage utilizando MinIO."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        secure: bool = False,
        max_file_size_mb: int = 50,
        region: str | None = None,
    ) -> None:
        if not endpoint or not endpoint.strip():
            raise ValueError("O endpoint do MinIO é obrigatório.")

        if not access_key:
            raise ValueError("A chave de acesso do MinIO é obrigatória.")

        if not secret_key:
            raise ValueError("A chave secreta do MinIO é obrigatória.")

        if not bucket_name or not bucket_name.strip():
            raise ValueError("O nome do bucket é obrigatório.")

        if max_file_size_mb <= 0:
            raise ValueError("O tamanho máximo deve ser positivo.")

        self.bucket_name = bucket_name.strip()
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

        self.client = Minio(
            endpoint=endpoint.strip(),
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region,
        )

        self._garantir_bucket()

    def _garantir_bucket(self) -> None:
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)

                logger.info(
                    "Bucket MinIO criado: bucket=%s",
                    self.bucket_name,
                )

        except S3Error as exc:
            logger.exception(
                "Falha ao verificar ou criar bucket MinIO: %s",
                self.bucket_name,
            )
            raise PdfStorageError(
                f"Não foi possível inicializar o bucket '{self.bucket_name}'."
            ) from exc

        except Exception as exc:
            logger.exception("Erro de conexão com o MinIO.")
            raise PdfStorageError(
                "Não foi possível inicializar o armazenamento MinIO."
            ) from exc

    def salvar(
        self,
        file_name: str,
        content: bytes | BinaryIO,
        checksum: str,
    ) -> PdfStorageMetadata:
        safe_file_name = self._validar_nome_arquivo(file_name)
        self._validar_checksum(checksum)

        pdf_content = self._ler_conteudo(content)

        if not pdf_content.startswith(b"%PDF-"):
            raise PdfStorageIntegrityError(
                "O conteúdo informado não possui uma assinatura PDF válida."
            )

        if len(pdf_content) > self.max_file_size_bytes:
            raise PdfStorageError(
                "O documento excede o tamanho máximo permitido."
            )

        calculated_checksum = hashlib.sha256(pdf_content).hexdigest()

        if calculated_checksum != checksum.lower():
            raise PdfStorageIntegrityError(
                "O checksum informado não corresponde ao conteúdo do PDF."
            )

        storage_key = f"{uuid4().hex}/{safe_file_name}"

        try:
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=storage_key,
                data=BytesIO(pdf_content),
                length=len(pdf_content),
                content_type="application/pdf",
                metadata={
                    "sha256": calculated_checksum,
                    "file-name": safe_file_name,
                },
            )

            logger.info(
                "PDF armazenado no MinIO: bucket=%s, key=%s, size=%d",
                self.bucket_name,
                storage_key,
                len(pdf_content),
            )

            return PdfStorageMetadata(
                storage_key=storage_key,
                file_name=safe_file_name,
                checksum=calculated_checksum,
                size_bytes=len(pdf_content),
                content_type="application/pdf",
                created_at=datetime.now(timezone.utc),
            )

        except S3Error as exc:
            logger.exception(
                "Falha ao armazenar PDF no MinIO: key=%s",
                storage_key,
            )
            raise PdfStorageError(
                "Não foi possível armazenar o documento no MinIO."
            ) from exc

        except Exception as exc:
            logger.exception(
                "Erro inesperado durante o armazenamento do PDF."
            )
            raise PdfStorageError(
                "Ocorreu um erro inesperado ao armazenar o documento."
            ) from exc

    def recuperar(self, storage_key: str) -> bytes:
        self._validar_storage_key(storage_key)

        try:
            response = self.client.get_object(
                bucket_name=self.bucket_name,
                object_name=storage_key,
            )

            try:
                content = response.read()
            finally:
                response.close()
                response.release_conn()

            if not content:
                raise PdfStorageIntegrityError(
                    "O documento armazenado está vazio."
                )

            if not content.startswith(b"%PDF-"):
                raise PdfStorageIntegrityError(
                    "O documento recuperado não possui uma assinatura PDF válida."
                )

            if len(content) > self.max_file_size_bytes:
                raise PdfStorageIntegrityError(
                    "O documento recuperado excede o tamanho máximo permitido."
                )

            metadata = self.obter_metadados(storage_key)

            calculated_checksum = hashlib.sha256(content).hexdigest()

            if calculated_checksum != metadata.checksum:
                raise PdfStorageIntegrityError(
                    "O checksum do documento recuperado não corresponde "
                    "ao checksum registrado no MinIO."
                )

            return content

        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                raise PdfNotFoundError(
                    f"Documento não encontrado: {storage_key}"
                ) from exc

            logger.exception(
                "Falha ao recuperar documento do MinIO: key=%s",
                storage_key,
            )
            raise PdfStorageError(
                "Não foi possível recuperar o documento do MinIO."
            ) from exc

        except (PdfNotFoundError, PdfStorageIntegrityError):
            raise

        except Exception as exc:
            logger.exception(
                "Erro inesperado durante a recuperação do PDF."
            )
            raise PdfStorageError(
                "Ocorreu um erro inesperado ao recuperar o documento."
            ) from exc

    def obter_metadados(
        self,
        storage_key: str,
    ) -> PdfStorageMetadata:
        self._validar_storage_key(storage_key)

        try:
            stat = self.client.stat_object(
                bucket_name=self.bucket_name,
                object_name=storage_key,
            )

            checksum = stat.metadata.get("x-amz-meta-sha256")

            if not checksum:
                raise PdfStorageIntegrityError(
                    "O documento não possui checksum registrado no MinIO."
                )

            file_name = stat.metadata.get("x-amz-meta-file-name")

            if not file_name:
                file_name = PurePosixPath(storage_key).name

            created_at = stat.last_modified or datetime.now(timezone.utc)

            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            return PdfStorageMetadata(
                storage_key=storage_key,
                file_name=file_name,
                checksum=checksum,
                size_bytes=stat.size,
                content_type=stat.content_type or "application/pdf",
                created_at=created_at,
            )

        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                raise PdfNotFoundError(
                    f"Documento não encontrado: {storage_key}"
                ) from exc

            logger.exception(
                "Falha ao consultar metadados no MinIO: key=%s",
                storage_key,
            )
            raise PdfStorageError(
                "Não foi possível consultar os metadados do documento."
            ) from exc

        except (PdfNotFoundError, PdfStorageIntegrityError):
            raise

        except Exception as exc:
            logger.exception(
                "Erro inesperado ao consultar metadados do PDF."
            )
            raise PdfStorageError(
                "Ocorreu um erro inesperado ao consultar os metadados."
            ) from exc

    def excluir(self, storage_key: str) -> None:
        self._validar_storage_key(storage_key)

        if not self.existe(storage_key):
            raise PdfNotFoundError(
                f"Documento não encontrado: {storage_key}"
            )

        try:
            self.client.remove_object(
                bucket_name=self.bucket_name,
                object_name=storage_key,
            )

            logger.info(
                "PDF removido do MinIO: bucket=%s, key=%s",
                self.bucket_name,
                storage_key,
            )

        except S3Error as exc:
            logger.exception(
                "Falha ao excluir documento do MinIO: key=%s",
                storage_key,
            )
            raise PdfStorageError(
                "Não foi possível excluir o documento do MinIO."
            ) from exc

    def existe(self, storage_key: str) -> bool:
        self._validar_storage_key(storage_key)

        try:
            self.client.stat_object(
                bucket_name=self.bucket_name,
                object_name=storage_key,
            )
            return True

        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject"}:
                return False

            if exc.code == "NoSuchBucket":
                raise PdfStorageError(
                    f"O bucket '{self.bucket_name}' não existe."
                ) from exc

            logger.exception(
                "Falha ao verificar existência do documento: key=%s",
                storage_key,
            )
            raise PdfStorageError(
                "Não foi possível verificar a existência do documento."
            ) from exc

        except Exception as exc:
            logger.exception(
                "Erro inesperado ao verificar documento no MinIO."
            )
            raise PdfStorageError(
                "Ocorreu um erro inesperado ao verificar o documento."
            ) from exc

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

    def _ler_conteudo(self, content: bytes | BinaryIO) -> bytes:
        if isinstance(content, bytes):
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
    def _validar_storage_key(storage_key: str) -> None:
        if not storage_key or not storage_key.strip():
            raise ValueError("O storage_key é obrigatório.")

        path = PurePosixPath(storage_key)

        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in storage_key
            or storage_key.startswith("/")
        ):
            raise ValueError("O storage_key informado é inválido.")
