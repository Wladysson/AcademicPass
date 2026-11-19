from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from enum import Enum
from typing import Any, Mapping
from uuid import UUID


class QuestionDocumentMappingError(Exception):
    """Erro durante a transformação de um evento em documento."""


class QuestionDocumentMapper:
    """Converte eventos do Kafka em documentos indexáveis."""

    def mapear(self, event: Mapping[str, Any] | Any) -> dict[str, Any]:
        """Transforma um evento estruturado em um documento Elasticsearch."""
        payload = self._to_dict(event)

        self._validar_evento(payload)

        question = self._to_dict(payload["question"])
        metadata = self._to_dict(question.get("metadata", {}))

        document = {
            "question_id": self._texto_obrigatorio(
                question.get("question_id"),
                "question.question_id",
            ),
            "event_id": self._texto_obrigatorio(
                payload.get("event_id"),
                "event_id",
            ),
            "event_type": payload.get("event_type"),
            "schema_version": payload.get("schema_version"),
            "published_at": self._data_iso(
                payload.get("published_at")
            ),
            "document_checksum": self._texto_obrigatorio(
                payload.get("document_checksum"),
                "document_checksum",
            ),
            "storage_key": self._texto_obrigatorio(
                payload.get("storage_key"),
                "storage_key",
            ),
            "question_number": question.get("question_number"),
            "question_type": self._enum_value(
                question.get("question_type")
            ),
            "statement": self._normalizar_texto(
                question.get("statement")
            ),
            "base_text": self._normalizar_texto(
                question.get("base_text")
            ),
            "alternatives": self._mapear_alternativas(
                question.get("alternatives", [])
            ),
            "correct_answer": self._normalizar_texto(
                question.get("correct_answer")
            ),
            "answer_status": self._enum_value(
                question.get("answer_status")
            ),
            "start_page": question.get("start_page"),
            "end_page": question.get("end_page"),
            "metadata": self._normalizar_valor(metadata),
            "formulas": self._normalizar_lista(
                question.get("formulas", [])
            ),
            "diagrams": self._normalizar_lista(
                question.get("diagrams", [])
            ),
            "tables": self._normalizar_lista(
                question.get("tables", [])
            ),
        }

        document["search_text"] = self._criar_texto_busca(document)

        return self._normalizar_valor(document)

    def mapear_lote(
        self,
        events: list[Mapping[str, Any] | Any],
    ) -> list[dict[str, Any]]:
        """Transforma uma coleção de eventos em documentos."""
        return [self.mapear(event) for event in events]

    def criar_document_id(
        self,
        document: Mapping[str, Any],
    ) -> str:
        """Retorna o identificador determinístico do documento."""
        question_id = document.get("question_id")

        if not isinstance(question_id, str) or not question_id.strip():
            raise QuestionDocumentMappingError(
                "O documento precisa conter um question_id válido."
            )

        return question_id

    @staticmethod
    def _to_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)

        if hasattr(value, "model_dump"):
            result = value.model_dump(mode="json")
            if isinstance(result, dict):
                return result

        if hasattr(value, "__dataclass_fields__"):
            from dataclasses import asdict

            result = asdict(value)
            if isinstance(result, dict):
                return result

        raise QuestionDocumentMappingError(
            "O evento ou objeto recebido não possui uma estrutura compatível."
        )

    @staticmethod
    def _validar_evento(payload: dict[str, Any]) -> None:
        required_fields = (
            "event_id",
            "event_type",
            "question_id",
            "document_checksum",
            "storage_key",
            "question",
        )

        missing_fields = [
            field
            for field in required_fields
            if payload.get(field) is None
        ]

        if missing_fields:
            raise QuestionDocumentMappingError(
                "Campos obrigatórios ausentes no evento: "
                + ", ".join(missing_fields)
            )

        if payload["event_type"] != "enade.questions.structured":
            raise QuestionDocumentMappingError(
                "Tipo de evento incompatível com a indexação de questões."
            )

        if not isinstance(payload["question"], Mapping) and not hasattr(
            payload["question"], "model_dump"
        ):
            raise QuestionDocumentMappingError(
                "O campo question precisa ser um objeto."
            )

    @staticmethod
    def _texto_obrigatorio(value: Any, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise QuestionDocumentMappingError(
                f"O campo {field} precisa ser um texto não vazio."
            )

        return value.strip()

    @staticmethod
    def _normalizar_texto(value: Any) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise QuestionDocumentMappingError(
                "Um campo textual recebeu um valor incompatível."
            )

        text = value.replace("\x00", "")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = unicodedata.normalize("NFC", text)

        return text.strip() or None

    @staticmethod
    def _enum_value(value: Any) -> str | None:
        if value is None:
            return None

        if isinstance(value, Enum):
            return str(value.value)

        return str(value)

    def _mapear_alternativas(self, alternatives: Any) -> list[dict[str, Any]]:
        if alternatives is None:
            return []

        if not isinstance(alternatives, (list, tuple)):
            raise QuestionDocumentMappingError(
                "O campo alternatives precisa ser uma lista."
            )

        mapped = []

        for alternative in alternatives:
            item = self._to_dict(alternative)

            label = self._texto_obrigatorio(
                item.get("label"),
                "alternative.label",
            )

            text = self._normalizar_texto(item.get("text"))

            if text is None:
                raise QuestionDocumentMappingError(
                    f"A alternativa {label} não possui texto."
                )

            mapped.append(
                {
                    "label": label.upper(),
                    "text": text,
                }
            )

        return mapped

    def _normalizar_lista(self, value: Any) -> list[Any]:
        if value is None:
            return []

        if not isinstance(value, (list, tuple)):
            raise QuestionDocumentMappingError(
                "Um campo de conteúdo multimídia precisa ser uma lista."
            )

        return [
            self._normalizar_valor(item)
            for item in value
        ]

    def _normalizar_valor(self, value: Any) -> Any:
        if isinstance(value, Enum):
            return self._normalizar_valor(value.value)

        if isinstance(value, UUID):
            return str(value)

        if isinstance(value, (datetime, date)):
            return value.isoformat()

        if isinstance(value, Mapping):
            return {
                str(key): self._normalizar_valor(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple)):
            return [
                self._normalizar_valor(item)
                for item in value
            ]

        if hasattr(value, "model_dump"):
            return self._normalizar_valor(
                value.model_dump(mode="json")
            )

        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)

        if value is None or isinstance(value, (bool, int, float)):
            return value

        raise QuestionDocumentMappingError(
            f"Tipo de dado não suportado: {type(value).__name__}."
        )

    @staticmethod
    def _data_iso(value: Any) -> str | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, str):
            return value

        raise QuestionDocumentMappingError(
            "O campo published_at precisa ser uma data ou texto ISO 8601."
        )

    @staticmethod
    def _criar_texto_busca(document: Mapping[str, Any]) -> str:
        """Consolida os campos textuais para facilitar pesquisas."""
        parts: list[str] = []

        for field in ("statement", "base_text", "correct_answer"):
            value = document.get(field)
            if isinstance(value, str) and value.strip():
                parts.append(value)

        for alternative in document.get("alternatives", []):
            parts.append(
                f"{alternative['label']} {alternative['text']}"
            )

        metadata = document.get("metadata", {})

        if isinstance(metadata, Mapping):
            for value in metadata.values():
                if isinstance(value, str) and value.strip():
                    parts.append(value)

        return re.sub(r"\s+", " ", " ".join(parts)).strip()
