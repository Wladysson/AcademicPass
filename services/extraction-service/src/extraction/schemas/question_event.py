from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class QuestionEventType(str, Enum):
    STRUCTURED = "enade.questions.structured"


class QuestionType(str, Enum):
    OBJECTIVE = "objective"
    DISCURSIVE = "discursive"
    UNKNOWN = "unknown"


class AnswerStatus(str, Enum):
    CORRECT = "correct"
    ANNULLED = "annulled"
    UNAVAILABLE = "unavailable"


class ExamComponent(str, Enum):
    GENERAL_EDUCATION = "general_education"
    SPECIFIC_COMPONENT = "specific_component"
    UNKNOWN = "unknown"


class EventSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        use_enum_values=True,
    )


class QuestionAlternative(EventSchema):
    label: str = Field(min_length=1, max_length=5)
    text: str = Field(min_length=1)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        return value.strip().upper()


class QuestionCompetency(EventSchema):
    code: str | None = None
    description: str = Field(min_length=1)
    area: str | None = None


class QuestionMetadata(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        use_enum_values=True,
    )

    area: str | None = None
    course_code: str | None = None
    course_name: str | None = None
    edition_year: int | None = Field(default=None, ge=1900, le=2200)
    exam_component: ExamComponent = ExamComponent.UNKNOWN
    document_type: str | None = None
    source_id: str | None = None
    source_name: str | None = None
    competencies: list[QuestionCompetency] = Field(default_factory=list)

    @field_validator("exam_component", mode="before")
    @classmethod
    def normalize_exam_component(cls, value: Any) -> Any:
        if value is None:
            return ExamComponent.UNKNOWN

        if isinstance(value, ExamComponent):
            return value

        normalized = str(value).strip().lower()

        aliases = {
            "fg": ExamComponent.GENERAL_EDUCATION,
            "formacao_geral": ExamComponent.GENERAL_EDUCATION,
            "formação geral": ExamComponent.GENERAL_EDUCATION,
            "general_education": ExamComponent.GENERAL_EDUCATION,
            "ce": ExamComponent.SPECIFIC_COMPONENT,
            "componente_especifico": ExamComponent.SPECIFIC_COMPONENT,
            "componente específico": ExamComponent.SPECIFIC_COMPONENT,
            "specific_component": ExamComponent.SPECIFIC_COMPONENT,
            "unknown": ExamComponent.UNKNOWN,
        }

        return aliases.get(normalized, normalized)


class QuestionContent(EventSchema):
    question_id: str = Field(min_length=1)
    question_number: int = Field(ge=1)

    question_type: QuestionType = QuestionType.UNKNOWN
    statement: str = Field(min_length=1)
    base_text: str | None = None

    alternatives: list[QuestionAlternative] = Field(default_factory=list)
    correct_answer: str | None = None
    answer_status: AnswerStatus = AnswerStatus.UNAVAILABLE

    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)

    metadata: QuestionMetadata = Field(default_factory=QuestionMetadata)

    formulas: list[dict[str, Any]] = Field(default_factory=list)
    diagrams: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_extraction_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        data = dict(value)

        aliases = {
            "question_number": ("number", "numero"),
            "statement": ("question_text", "text", "enunciado"),
            "base_text": ("shared_text", "supporting_text"),
            "start_page": ("page_start",),
            "end_page": ("page_end",),
        }

        for target, alternatives in aliases.items():
            if target not in data:
                for alias in alternatives:
                    if alias in data:
                        data[target] = data[alias]
                        break

        classification = data.get("classification")

        if classification is not None:
            if hasattr(classification, "model_dump"):
                classification = classification.model_dump()
            elif hasattr(classification, "__dict__"):
                classification = vars(classification)

            if isinstance(classification, dict):
                for field in ("question_type", "answer_status"):
                    if field not in data and field in classification:
                        data[field] = classification[field]

        return data

    @field_validator("question_type", mode="before")
    @classmethod
    def normalize_question_type(cls, value: Any) -> Any:
        if value is None:
            return QuestionType.UNKNOWN

        if isinstance(value, QuestionType):
            return value

        normalized = str(value).strip().lower()

        aliases = {
            "objective": QuestionType.OBJECTIVE,
            "objetiva": QuestionType.OBJECTIVE,
            "discursive": QuestionType.DISCURSIVE,
            "discursiva": QuestionType.DISCURSIVE,
            "unknown": QuestionType.UNKNOWN,
            "desconhecida": QuestionType.UNKNOWN,
        }

        return aliases.get(normalized, normalized)

    @field_validator("answer_status", mode="before")
    @classmethod
    def normalize_answer_status(cls, value: Any) -> Any:
        if value is None:
            return AnswerStatus.UNAVAILABLE

        if isinstance(value, AnswerStatus):
            return value

        normalized = str(value).strip().lower()

        aliases = {
            "correct": AnswerStatus.CORRECT,
            "disponivel": AnswerStatus.CORRECT,
            "disponível": AnswerStatus.CORRECT,
            "annulled": AnswerStatus.ANNULLED,
            "anulada": AnswerStatus.ANNULLED,
            "anulado": AnswerStatus.ANNULLED,
            "unavailable": AnswerStatus.UNAVAILABLE,
            "indisponivel": AnswerStatus.UNAVAILABLE,
            "indisponível": AnswerStatus.UNAVAILABLE,
        }

        return aliases.get(normalized, normalized)

    @field_validator("correct_answer")
    @classmethod
    def normalize_correct_answer(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip().upper()
        return normalized or None

    @field_validator("alternatives")
    @classmethod
    def validate_alternative_labels(
        cls,
        alternatives: list[QuestionAlternative],
    ) -> list[QuestionAlternative]:
        labels = [alternative.label for alternative in alternatives]

        if len(labels) != len(set(labels)):
            raise ValueError("As alternativas não podem possuir rótulos duplicados.")

        return alternatives

    @model_validator(mode="after")
    def validate_question_consistency(self) -> QuestionContent:
        if self.end_page < self.start_page:
            raise ValueError("A página final não pode ser anterior à página inicial.")

        labels = {alternative.label for alternative in self.alternatives}

        if self.question_type == QuestionType.OBJECTIVE:
            if len(self.alternatives) < 2:
                raise ValueError(
                    "Questões objetivas devem possuir pelo menos duas alternativas."
                )

        if self.question_type == QuestionType.DISCURSIVE and self.alternatives:
            raise ValueError(
                "Questões discursivas não devem possuir alternativas objetivas."
            )

        if self.answer_status == AnswerStatus.ANNULLED and self.correct_answer:
            raise ValueError(
                "Questões anuladas não podem possuir resposta correta."
            )

        if self.correct_answer and self.correct_answer not in labels:
            raise ValueError(
                "A resposta correta deve corresponder a uma alternativa existente."
            )

        return self


class QuestionEvent(EventSchema):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: QuestionEventType = QuestionEventType.STRUCTURED
    schema_version: str = "1.0"

    published_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Identificação e rastreabilidade do documento
    question_id: str = Field(min_length=1)
    document_checksum: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    storage_key: str = Field(min_length=1)

    # Conteúdo estruturado da questão
    question: QuestionContent

    @field_validator("published_at")
    @classmethod
    def validate_published_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("published_at deve possuir informação de fuso horário.")

        return value

    @field_validator("document_checksum")
    @classmethod
    def normalize_checksum(cls, value: str) -> str:
        return value.lower()

    @field_validator("storage_key")
    @classmethod
    def validate_storage_key(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("storage_key não pode ser vazio.")

        if normalized.startswith("/") or "\\" in normalized:
            raise ValueError("storage_key deve ser uma chave relativa válida.")

        if any(part in {"", ".", ".."} for part in normalized.split("/")):
            raise ValueError("storage_key contém segmentos inválidos.")

        return normalized

    @model_validator(mode="after")
    def validate_question_id(self) -> QuestionEvent:
        if self.event.question_id != self.question_id:
            raise ValueError(
                "question_id do evento deve corresponder ao question_id da questão."
            )

        return self

    def to_kafka_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_kafka_payload(cls, payload: dict[str, Any]) -> QuestionEvent:
        return cls.model_validate(payload)
