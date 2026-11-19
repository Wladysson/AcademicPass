from __future__ import annotations

import logging
from typing import Any

from minio import Minio
from minio.error import S3Error

from extraction.storage.pdf_reader import (
    PdfDocument,
    PdfIntegrityError,
    PdfNotFoundError,
    PdfReader,
    PdfReaderError,
)

logger = logging.getLogger(__name__)


class MinioPdfReader(PdfReader):
    """Implementa a recuperação de PDFs armazenados no MinIO."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        secure: bool = False,
        region: str | None = None,
        max_file_size_mb: int = 50,
        client: Minio | None = None,
    ) -> None:
        if not endpoint.strip():
            raise ValueError("O endpoint do MinIO é obrigatório.")

        if not access_key:
            raise ValueError("A chave de acesso do MinIO é obrigatória.")

        if not secret_key:
            raise ValueError("A chave secreta do MinIO é obrigatória.")

        if not bucket_name.strip():
            raise ValueError("O nome do bucket é obrigatório.")

        if max_file_size_mb <= 0:
            raise ValueError("O limite de tamanho precisa ser positivo.")

        self._bucket_name = bucket_name
        self._max_file_size_bytes = max_file_size_mb * 1024 * 1024

        try:
            self._client = client or Minio(
                endpoint=endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
                region=region,
            )
        except Exception as exc:
            raise PdfReaderError(
                "Não foi possível inicializar o cliente MinIO."
            ) from exc

    def recuperar(
        self,
        storage_key: str,
        checksum: str,
    ) -> PdfDocument:
        self.validar_storage_key(storage_key)
        self.validar_checksum(checksum)

        response = None

        try:
            stat = self._client.stat_object(
                self._bucket_name,
                storage_key,
            )

            if stat.size <= 0:
                raise PdfIntegrityError(
                    "O documento armazenado possui tamanho inválido."
                )

            if stat.size > self._max_file_size_bytes:
                raise PdfIntegrityError(
                    "O documento excede o limite de tamanho permitido."
                )

            if stat.content_type != "application/pdf":
                raise PdfIntegrityError(
                    "O objeto armazenado não está identificado como PDF."
                )

            response = self._client.get_object(
                self._bucket_name,
                storage_key,
            )

            content = response.read(self._max_file_size_bytes + 1)

            if len(content) > self._max_file_size_bytes:
                raise PdfIntegrityError(
                    "O documento excede o limite de leitura permitido."
                )

            if len(content) != stat.size:
                raise PdfIntegrityError(
                    "O tamanho recuperado não corresponde ao tamanho armazenado."
                )

            metadata = self._normalizar_metadados(stat.metadata or {})

            stored_checksum = metadata.get("sha256")

            if stored_checksum and stored_checksum.lower() != checksum.lower():
                raise PdfIntegrityError(
                    "O checksum informado diverge dos metadados do MinIO."
                )

            file_name = metadata.get("file-name")

            if not file_name:
                file_name = storage_key.rsplit("/", 1)[-1]

            document = self.criar_documento(
                storage_key=storage_key,
                file_name=file_name,
                content=content,
                checksum=checksum,
                content_type=stat.content_type,
            )

            logger.info(
                "PDF recuperado do MinIO. storage_key=%s size_bytes=%s",
                storage_key,
                document.size_bytes,
            )

            return document

        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                raise PdfNotFoundError(
                    f"Documento não encontrado no MinIO: {storage_key}"
                ) from exc

            logger.exception(
                "Falha ao recuperar PDF do MinIO. storage_key=%s",
                storage_key,
            )

            raise PdfReaderError(
                "Erro durante a recuperação do documento no MinIO."
            ) from exc

        except (PdfIntegrityError, PdfNotFoundError, ValueError):
            raise

        except Exception as exc:
            logger.exception(
                "Erro inesperado na leitura do PDF. storage_key=%s",
                storage_key,
            )

            raise PdfReaderError(
                "Não foi possível recuperar o documento PDF."
            ) from exc

        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def existe(self, storage_key: str) -> bool:
        self.validar_storage_key(storage_key)

        try:
            self._client.stat_object(
                self._bucket_name,
                storage_key,
            )
            return True

        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject"}:
                return False

            if exc.code == "NoSuchBucket":
                raise PdfReaderError(
                    "O bucket configurado não existe no MinIO."
                ) from exc

            raise PdfReaderError(
                "Não foi possível verificar a existência do documento."
            ) from exc

        except Exception as exc:
            raise PdfReaderError(
                "Falha ao consultar o documento no MinIO."
            ) from exc

    def obter_metadados(
        self,
        storage_key: str,
    ) -> dict[str, str | int | None]:
        self.validar_storage_key(storage_key)

        try:
            stat = self._client.stat_object(
                self._bucket_name,
                storage_key,
            )

            metadata = self._normalizar_metadados(
                stat.metadata or {}
            )

            return {
                "storage_key": storage_key,
                "file_name": metadata.get(
                    "file-name",
                    storage_key.rsplit("/", 1)[-1],
                ),
                "checksum": metadata.get("sha256"),
                "size_bytes": stat.size,
                "content_type": stat.content_type,
                "last_modified": (
                    stat.last_modified.isoformat()
                    if stat.last_modified
                    else None
                ),
                "etag": stat.etag,
            }

        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                raise PdfNotFoundError(
                    f"Documento não encontrado no MinIO: {storage_key}"
                ) from exc

            raise PdfReaderError(
                "Não foi possível recuperar os metadados do documento."
            ) from exc

        except Exception as exc:
            raise PdfReaderError(
                "Falha ao consultar os metadados no MinIO."
            ) from exc

    @staticmethod
    def _normalizar_metadados(
        metadata: dict[str, Any],
    ) -> dict[str, str]:
        normalized: dict[str, str] = {}

        for key, value in metadata.items():
            normalized_key = key.lower()

            if normalized_key.startswith("x-amz-meta-"):
                normalized_key = normalized_key.removeprefix(
                    "x-amz-meta-"
                )

            normalized[normalized_key] = str(value)

        return normalized
