from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from urllib.parse import urlparse


class PdfDiscoveredEventError(Exception):
    """Erro relacionado à criação ou serialização do evento."""


class PdfDocumentType(str, Enum):
    EXAM = "exam"
    ANSWER_KEY = "answer_key"
    GUIDELINE = "guideline"


@dataclass(frozen=True, slots=True)
class PdfDocumentMetadata:
    source_id: str
    source_name: str
    course_code: str
    course_name: str
    edition_year: int
    document_type: PdfDocumentType
    source_url: str

    def __post_init__(self) -> None:
        required_fields = {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "course_code": self.course_code,
            "course_name": self.course_name,
            "source_url": self.source_url,
        }

        for field_name, value in required_fields.items():
            if not isinstance(value, str) or not value.strip():
                raise PdfDiscoveredEventError(
                    f"O campo '{field_name}' é obrigatório."
                )

        if not isinstance(self.edition_year, int) or isinstance(
            self.edition_year, bool
        ):
            raise PdfDiscoveredEventError(
                "O ano da edição deve ser um número inteiro."
            )

        if self.edition_year < 2004:
            raise PdfDiscoveredEventError(
                "O ano da edição informado é inválido."
            )

        if not isinstance(self.document_type, PdfDocumentType):
            raise PdfDiscoveredEventError(
                "O tipo de documento informado é inválido."
            )

        parsed_url = urlparse(self.source_url)

        if parsed_url.scheme != "https" or not parsed_url.hostname:
            raise PdfDiscoveredEventError(
                "A URL de origem deve utilizar HTTPS."
            )

        if parsed_url.username or parsed_url.password:
            raise PdfDiscoveredEventError(
                "A URL de origem não pode conter credenciais."
            )


@dataclass(frozen=True, slots=True)
class PdfDiscoveredEvent:
    event_id: str
    storage_key: str
    checksum: str
    size_bytes: int
    file_name: str
    content_type: str
    metadata: PdfDocumentMetadata
    discovered_at: datetime
    schema_version: str = "1.0"
    attributes: dict[str, Any] = field(default_factory=dict)

    EVENT_TYPE = "enade.pdf.discovered"

    def __post_init__(self) -> None:
        if not self.event_id or not self.event_id.strip():
            raise PdfDiscoveredEventError(
                "O identificador do evento é obrigatório."
            )

        if not re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{12}",
            self.event_id,
        ):
            raise PdfDiscoveredEventError(
                "O event_id deve ser um UUID válido."
            )

        if not self.storage_key or not self.storage_key.strip():
            raise PdfDiscoveredEventError(
                "O storage_key é obrigatório."
            )

        self._validar_storage_key(self.storage_key)

        if not isinstance(self.checksum, str) or not re.fullmatch(
            r"[a-fA-F0-9]{64}",
            self.checksum,
        ):
            raise PdfDiscoveredEventError(
                "O checksum deve ser um SHA-256 hexadecimal válido."
            )

        if not isinstance(self.size_bytes, int) or isinstance(
            self.size_bytes, bool
        ):
            raise PdfDiscoveredEventError(
                "O tamanho do documento deve ser um número inteiro."
            )

        if self.size_bytes <= 0:
            raise PdfDiscoveredEventError(
                "O tamanho do documento deve ser positivo."
            )

        if not self.file_name or not self.file_name.strip():
            raise PdfDiscoveredEventError(
                "O nome do arquivo é obrigatório."
            )

        if "/" in self.file_name or "\\" in self.file_name:
            raise PdfDiscoveredEventError(
                "O nome do arquivo não pode conter separadores."
            )

        if not self.file_name.lower().endswith(".pdf"):
            raise PdfDiscoveredEventError(
                "O arquivo precisa possuir extensão PDF."
            )

        if self.content_type != "application/pdf":
            raise PdfDiscoveredEventError(
                "O content type deve ser application/pdf."
            )

        if not isinstance(self.metadata, PdfDocumentMetadata):
            raise PdfDiscoveredEventError(
                "Os metadados do documento são obrigatórios."
            )

        if self.discovered_at.tzinfo is None:
            raise PdfDiscoveredEventError(
                "A data de descoberta deve possuir fuso horário."
            )

        if not self.schema_version or not self.schema_version.strip():
            raise PdfDiscoveredEventError(
                "A versão do esquema do evento é obrigatória."
            )

        if not isinstance(self.attributes, dict):
            raise PdfDiscoveredEventError(
                "Os atributos adicionais devem ser um objeto JSON."
            )

        try:
            json.dumps(self.attributes)
        except (TypeError, ValueError) as exc:
            raise PdfDiscoveredEventError(
                "Os atributos adicionais precisam ser serializáveis em JSON."
            ) from exc

    @staticmethod
    def _validar_storage_key(storage_key: str) -> None:
        if (
            storage_key.startswith("/")
            or "\\" in storage_key
            or ".." in storage_key.split("/")
            or any(not part for part in storage_key.split("/"))
        ):
            raise PdfDiscoveredEventError(
                "O storage_key informado é inválido."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.EVENT_TYPE,
            "schema_version": self.schema_version,
            "storage_key": self.storage_key,
            "checksum": self.checksum.lower(),
            "size_bytes": self.size_bytes,
            "file_name": self.file_name,
            "content_type": self.content_type,
            "metadata": {
                "source_id": self.metadata.source_id,
                "source_name": self.metadata.source_name,
                "course_code": self.metadata.course_code,
                "course_name": self.metadata.course_name,
                "edition_year": self.metadata.edition_year,
                "document_type": self.metadata.document_type.value,
                "source_url": self.metadata.source_url,
            },
            "discovered_at": self.discovered_at.astimezone(
                timezone.utc
            ).isoformat(),
            "attributes": self.attributes,
        }

    def to_json(self) -> str:
        try:
            return json.dumps(
                self.to_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise PdfDiscoveredEventError(
                "Não foi possível serializar o evento para JSON."
            ) from exc

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PdfDiscoveredEvent:
        if not isinstance(data, dict):
            raise PdfDiscoveredEventError(
                "O conteúdo do evento deve ser um objeto JSON."
            )

        if data.get("event_type") != cls.EVENT_TYPE:
            raise PdfDiscoveredEventError(
                "O tipo do evento recebido é incompatível."
            )

        metadata_data = data.get("metadata")

        if not isinstance(metadata_data, dict):
            raise PdfDiscoveredEventError(
                "Os metadados do evento estão ausentes ou inválidos."
            )

        try:
            metadata = PdfDocumentMetadata(
                source_id=metadata_data["source_id"],
                source_name=metadata_data["source_name"],
                course_code=metadata_data["course_code"],
                course_name=metadata_data["course_name"],
                edition_year=metadata_data["edition_year"],
                document_type=PdfDocumentType(
                    metadata_data["document_type"]
                ),
                source_url=metadata_data["source_url"],
            )

            return cls(
                event_id=data["event_id"],
                storage_key=data["storage_key"],
                checksum=data["checksum"],
                size_bytes=data["size_bytes"],
                file_name=data["file_name"],
                content_type=data["content_type"],
                metadata=metadata,
                discovered_at=datetime.fromisoformat(
                    data["discovered_at"]
                ),
                schema_version=data.get("schema_version", "1.0"),
                attributes=data.get("attributes", {}),
            )

        except (KeyError, TypeError, ValueError) as exc:
            raise PdfDiscoveredEventError(
                "Não foi possível reconstruir o evento a partir dos dados."
            ) from exc

    @classmethod
    def from_json(cls, payload: str) -> PdfDiscoveredEvent:
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, TypeError) as exc:
            raise PdfDiscoveredEventError(
                "O conteúdo recebido não é um JSON válido."
            ) from exc

        return cls.from_dict(data)

    @classmethod
    def criar(
        cls,
        storage_key: str,
        checksum: str,
        size_bytes: int,
        file_name: str,
        metadata: PdfDocumentMetadata,
        attributes: dict[str, Any] | None = None,
    ) -> PdfDiscoveredEvent:
        from uuid import uuid4

        return cls(
            event_id=str(uuid4()),
            storage_key=storage_key,
            checksum=checksum,
            size_bytes=size_bytes,
            file_name=file_name,
            content_type="application/pdf",
            metadata=metadata,
            discovered_at=datetime.now(timezone.utc),
            attributes=attributes or {},
        )
