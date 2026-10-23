from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

import httpx

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    EXAM = "exam"
    ANSWER_KEY = "answer_key"
    GUIDELINE = "guideline"


@dataclass(frozen=True, slots=True)
class DownloadedDocument:
    source_url: str
    file_name: str
    document_type: DocumentType
    content: bytes
    checksum: str
    size_bytes: int
    content_type: str
    downloaded_at: datetime


class EnaDeDownloaderError(Exception):
    """Erro durante a obtenção de documentos do ENADE."""


class EnaDeDownloader:
    PDF_SIGNATURE = b"%PDF-"

    DEFAULT_USER_AGENT = (
        "AcademicPass-IngestionService/1.0 "
        "(ENADE document collection)"
    )

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        max_file_size_mb: int = 50,
        max_retries: int = 3,
        chunk_size: int = 64 * 1024,
        allowed_domains: tuple[str, ...] = (),
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("O timeout deve ser maior que zero.")

        if max_file_size_mb <= 0:
            raise ValueError("O tamanho máximo deve ser maior que zero.")

        if max_retries < 1:
            raise ValueError("O número de tentativas deve ser pelo menos 1.")

        if chunk_size <= 0:
            raise ValueError("O tamanho do bloco deve ser maior que zero.")

        self.timeout_seconds = timeout_seconds
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.max_retries = max_retries
        self.chunk_size = chunk_size
        self.allowed_domains = tuple(
            domain.lower().strip(".")
            for domain in allowed_domains
            if domain.strip()
        )
        self.user_agent = user_agent

        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/pdf,application/octet-stream;q=0.9",
            },
        )

    def baixar_documento(
        self,
        url: str,
        document_type: DocumentType,
        file_name: str | None = None,
    ) -> DownloadedDocument:
        self._validar_url(url)

        if not isinstance(document_type, DocumentType):
            raise ValueError("Tipo de documento inválido.")

        resolved_file_name = self._resolver_nome_arquivo(
            url=url,
            file_name=file_name,
        )

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            started_at = time.perf_counter()

            try:
                document = self._executar_download(
                    url=url,
                    document_type=document_type,
                    file_name=resolved_file_name,
                )

                elapsed = time.perf_counter() - started_at

                logger.info(
                    "Documento ENADE baixado com sucesso: "
                    "tipo=%s, arquivo=%s, tamanho=%d bytes, "
                    "checksum=%s, duracao=%.2fs",
                    document.document_type.value,
                    document.file_name,
                    document.size_bytes,
                    document.checksum,
                    elapsed,
                )

                return document

            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.RemoteProtocolError,
            ) as exc:
                last_error = exc

                logger.warning(
                    "Falha de comunicação no download: "
                    "tentativa=%d/%d, url=%s, erro=%s",
                    attempt,
                    self.max_retries,
                    url,
                    str(exc),
                )

                if attempt < self.max_retries:
                    time.sleep(min(2 ** (attempt - 1), 8))

            except EnaDeDownloaderError:
                raise

            except httpx.HTTPError as exc:
                raise EnaDeDownloaderError(
                    f"Erro HTTP durante o download: {exc}"
                ) from exc

        raise EnaDeDownloaderError(
            f"Não foi possível baixar o documento após "
            f"{self.max_retries} tentativas."
        ) from last_error

    def _executar_download(
        self,
        url: str,
        document_type: DocumentType,
        file_name: str,
    ) -> DownloadedDocument:
        try:
            with self.client.stream("GET", url) as response:
                response.raise_for_status()

                content_length = response.headers.get("Content-Length")

                if content_length is not None:
                    try:
                        expected_size = int(content_length)
                    except ValueError as exc:
                        raise EnaDeDownloaderError(
                            "Content-Length retornado pela fonte é inválido."
                        ) from exc

                    if expected_size < 0:
                        raise EnaDeDownloaderError(
                            "Content-Length não pode ser negativo."
                        )

                    if expected_size > self.max_file_size_bytes:
                        raise EnaDeDownloaderError(
                            "O documento excede o tamanho máximo permitido."
                        )

                content_type = (
                    response.headers.get("Content-Type", "")
                    .split(";")[0]
                    .strip()
                    .lower()
                )

                chunks: list[bytes] = []
                total_size = 0
                checksum = hashlib.sha256()
                signature = bytearray()

                for chunk in response.iter_bytes(
                    chunk_size=self.chunk_size
                ):
                    if not chunk:
                        continue

                    total_size += len(chunk)

                    if total_size > self.max_file_size_bytes:
                        raise EnaDeDownloaderError(
                            "O documento excede o tamanho máximo permitido."
                        )

                    if len(signature) < len(self.PDF_SIGNATURE):
                        remaining = len(self.PDF_SIGNATURE) - len(signature)
                        signature.extend(chunk[:remaining])

                    checksum.update(chunk)
                    chunks.append(chunk)

                if total_size == 0:
                    raise EnaDeDownloaderError(
                        "A fonte retornou um documento vazio."
                    )

                if bytes(signature) != self.PDF_SIGNATURE:
                    raise EnaDeDownloaderError(
                        "O conteúdo recebido não possui uma assinatura PDF válida."
                    )

                content = b"".join(chunks)

                return DownloadedDocument(
                    source_url=url,
                    file_name=file_name,
                    document_type=document_type,
                    content=content,
                    checksum=checksum.hexdigest(),
                    size_bytes=total_size,
                    content_type="application/pdf",
                    downloaded_at=datetime.now(timezone.utc),
                )

        except httpx.HTTPStatusError as exc:
            raise EnaDeDownloaderError(
                f"A fonte retornou HTTP {exc.response.status_code}."
            ) from exc

    def _validar_url(self, url: str) -> None:
        if not url or not url.strip():
            raise ValueError("A URL do documento é obrigatória.")

        parsed_url = urlparse(url)

        if parsed_url.scheme != "https":
            raise ValueError(
                "Somente URLs HTTPS são permitidas para download."
            )

        if not parsed_url.hostname:
            raise ValueError("A URL informada não possui um domínio válido.")

        if parsed_url.username or parsed_url.password:
            raise ValueError(
                "URLs com credenciais embutidas não são permitidas."
            )

        if self.allowed_domains:
            hostname = parsed_url.hostname.lower().rstrip(".")

            if not any(
                hostname == domain
                or hostname.endswith(f".{domain}")
                for domain in self.allowed_domains
            ):
                raise ValueError(
                    "O domínio da URL não está na lista de fontes autorizadas."
                )

    @staticmethod
    def _resolver_nome_arquivo(
        url: str,
        file_name: str | None,
    ) -> str:
        if file_name:
            candidate = file_name.strip()
        else:
            parsed_url = urlparse(url)
            candidate = unquote(
                PurePosixPath(parsed_url.path).name
            )

        if not candidate:
            raise ValueError(
                "Não foi possível determinar o nome do documento."
            )

        if candidate in {".", ".."}:
            raise ValueError("Nome de arquivo inválido.")

        if "/" in candidate or "\\" in candidate:
            raise ValueError(
                "O nome do arquivo não pode conter separadores de diretório."
            )

        candidate = re.sub(r"[^a-zA-Z0-9._-]", "_", candidate)

        if not candidate.lower().endswith(".pdf"):
            candidate += ".pdf"

        return candidate

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> EnaDeDownloader:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
