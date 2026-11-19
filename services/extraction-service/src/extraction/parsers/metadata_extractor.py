from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

from extraction.parsers.pdf_parser import ParsedPdf
from extraction.parsers.question_segmenter import SegmentedQuestions


class MetadataExtractorError(Exception):
    """Erro durante a extração de metadados do documento."""


class MetadataConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class ExamComponent(str, Enum):
    GENERAL_FORMATION = "FG"
    SPECIFIC_COMPONENT = "CE"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ExtractedField:
    value: str | int | None
    confidence: MetadataConfidence
    source: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.value, str) and not self.value.strip():
            raise ValueError("O valor do metadado não pode ser uma string vazia.")


@dataclass(frozen=True)
class ExtractedCompetency:
    description: str
    identifier: str | None = None
    source: str = "document_text"
    confidence: MetadataConfidence = MetadataConfidence.MEDIUM

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("A descrição da competência é obrigatória.")


@dataclass(frozen=True)
class QuestionMetadata:
    question_number: int
    component: ExamComponent
    competencies: tuple[ExtractedCompetency, ...] = ()


@dataclass(frozen=True)
class DocumentMetadata:
    area: ExtractedField
    course: ExtractedField
    year: ExtractedField
    component: ExtractedField
    competencies: tuple[ExtractedCompetency, ...] = ()
    document_type: ExtractedField = field(
        default_factory=lambda: ExtractedField(
            value=None,
            confidence=MetadataConfidence.UNKNOWN,
        )
    )


@dataclass(frozen=True)
class MetadataExtractionResult:
    document: DocumentMetadata
    questions: tuple[QuestionMetadata, ...]
    storage_key: str | None
    checksum: str | None

    @property
    def has_complete_identification(self) -> bool:
        return all(
            extracted.value is not None
            for extracted in (
                self.document.course,
                self.document.year,
                self.document.component,
            )
        )


class MetadataExtractor:

    YEAR_PATTERN = re.compile(
        r"\b(?:ENADE\s*)?(?:EDIÇÃO|EDICAO|ANO)?\s*[:\-]?\s*"
        r"(20\d{2})\b",
        re.IGNORECASE,
    )

    COURSE_PATTERNS = (
        re.compile(
            r"\bCURSO\s*[:\-]\s*([^\n\r]{3,120})",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bGRADUAÇÃO\s+EM\s+([^\n\r]{3,120})",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bGRADUACAO\s+EM\s+([^\n\r]{3,120})",
            re.IGNORECASE,
        ),
    )

    AREA_PATTERNS = (
        re.compile(
            r"\bÁREA\s+DE\s+AVALIAÇÃO\s*[:\-]\s*([^\n\r]{3,120})",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bAREA\s+DE\s+AVALIACAO\s*[:\-]\s*([^\n\r]{3,120})",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bÁREA\s*[:\-]\s*([^\n\r]{3,120})",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bAREA\s*[:\-]\s*([^\n\r]{3,120})",
            re.IGNORECASE,
        ),
    )

    COMPETENCY_PATTERNS = (
        re.compile(
            r"\bCOMPETÊNCIA\s*(?:GERAL\s*)?"
            r"(?:N[º°.]?\s*(\d+))?\s*[:\-]\s*([^\n\r]{5,500})",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bCOMPETENCIA\s*(?:GERAL\s*)?"
            r"(?:N[º°.]?\s*(\d+))?\s*[:\-]\s*([^\n\r]{5,500})",
            re.IGNORECASE,
        ),
    )

    GENERAL_FORMATION_PATTERNS = (
        re.compile(r"\bFORMAÇÃO\s+GERAL\b", re.IGNORECASE),
        re.compile(r"\bFORMACAO\s+GERAL\b", re.IGNORECASE),
        re.compile(r"\bQUESTÕES?\s+DE\s+FORMAÇÃO\s+GERAL\b", re.IGNORECASE),
        re.compile(r"\bQUESTOES?\s+DE\s+FORMACAO\s+GERAL\b", re.IGNORECASE),
    )

    SPECIFIC_COMPONENT_PATTERNS = (
        re.compile(r"\bCOMPONENTE\s+ESPECÍFICO\b", re.IGNORECASE),
        re.compile(r"\bCOMPONENTE\s+ESPECIFICO\b", re.IGNORECASE),
        re.compile(r"\bQUESTÕES?\s+DO\s+COMPONENTE\s+ESPECÍFICO\b", re.IGNORECASE),
        re.compile(r"\bQUESTOES?\s+DO\s+COMPONENTE\s+ESPECIFICO\b", re.IGNORECASE),
    )

    DOCUMENT_TYPE_VALUES = {
        "prova": "exam",
        "gabarito": "answer_key",
        "questionario": "questionnaire",
        "questionário": "questionnaire",
        "caderno de questoes": "exam",
        "caderno de questões": "exam",
    }

    def extract(
        self,
        parsed_pdf: ParsedPdf,
        source_metadata: Mapping[str, Any] | None = None,
        segmented_questions: SegmentedQuestions | None = None,
    ) -> MetadataExtractionResult:

        if parsed_pdf is None:
            raise MetadataExtractorError("O documento PDF não foi informado.")

        trusted_metadata = self._normalize_mapping(source_metadata)
        pdf_metadata = self._normalize_mapping(
            getattr(parsed_pdf, "metadata", None)
        )
        full_text = str(getattr(parsed_pdf, "full_text", "") or "")

        if not full_text:
            full_text = self._extract_text_from_pages(
                getattr(parsed_pdf, "pages", ())
            )

        document = DocumentMetadata(
            area=self._extract_area(trusted_metadata, pdf_metadata, full_text),
            course=self._extract_course(trusted_metadata, pdf_metadata, full_text),
            year=self._extract_year(trusted_metadata, pdf_metadata, full_text),
            component=self._extract_component(
                trusted_metadata,
                pdf_metadata,
                full_text,
            ),
            competencies=self._extract_competencies(full_text),
            document_type=self._extract_document_type(
                trusted_metadata,
                pdf_metadata,
                full_text,
            ),
        )

        questions = self._extract_question_metadata(
            segmented_questions,
            full_text,
        )

        return MetadataExtractionResult(
            document=document,
            questions=questions,
            storage_key=getattr(parsed_pdf, "storage_key", None),
            checksum=getattr(parsed_pdf, "checksum", None),
        )

    def _extract_area(
        self,
        source: Mapping[str, Any],
        pdf: Mapping[str, Any],
        text: str,
    ) -> ExtractedField:
        value = self._first_value(
            source,
            ("area", "evaluation_area", "area_name", "area_avaliacao"),
        )
        if value:
            return self._field(value, MetadataConfidence.HIGH, "ingestion_event")

        value = self._first_value(
            pdf,
            ("subject", "area", "evaluation_area"),
        )
        if value:
            return self._field(value, MetadataConfidence.MEDIUM, "pdf_metadata")

        value = self._first_pattern_value(self.AREA_PATTERNS, text)
        if value:
            return self._field(value, MetadataConfidence.MEDIUM, "document_text")

        return self._unknown_field()

    def _extract_course(
        self,
        source: Mapping[str, Any],
        pdf: Mapping[str, Any],
        text: str,
    ) -> ExtractedField:
        value = self._first_value(
            source,
            ("course_name", "course", "curso", "course_title"),
        )
        if value:
            return self._field(value, MetadataConfidence.HIGH, "ingestion_event")

        value = self._first_value(pdf, ("course", "course_name"))
        if value:
            return self._field(value, MetadataConfidence.MEDIUM, "pdf_metadata")

        value = self._first_pattern_value(self.COURSE_PATTERNS, text)
        if value:
            return self._field(value, MetadataConfidence.MEDIUM, "document_text")

        return self._unknown_field()

    def _extract_year(
        self,
        source: Mapping[str, Any],
        pdf: Mapping[str, Any],
        text: str,
    ) -> ExtractedField:
        value = self._first_value(
            source,
            ("edition_year", "year", "ano", "exam_year"),
        )
        year = self._parse_year(value)
        if year is not None:
            return self._field(year, MetadataConfidence.HIGH, "ingestion_event")

        value = self._first_value(pdf, ("year", "edition_year", "creation_date"))
        year = self._parse_year(value)
        if year is not None:
            return self._field(year, MetadataConfidence.MEDIUM, "pdf_metadata")

        match = self.YEAR_PATTERN.search(text)
        if match:
            return self._field(
                int(match.group(1)),
                MetadataConfidence.MEDIUM,
                "document_text",
            )

        return self._unknown_field()

    def _extract_component(
        self,
        source: Mapping[str, Any],
        pdf: Mapping[str, Any],
        text: str,
    ) -> ExtractedField:
        value = self._first_value(
            source,
            ("component", "exam_component", "exam_section", "fg_ce"),
        )
        component = self._parse_component(value)
        if component is not ExamComponent.UNKNOWN:
            return self._field(
                component.value,
                MetadataConfidence.HIGH,
                "ingestion_event",
            )

        value = self._first_value(
            pdf,
            ("component", "exam_component", "subject"),
        )
        component = self._parse_component(value)
        if component is not ExamComponent.UNKNOWN:
            return self._field(
                component.value,
                MetadataConfidence.MEDIUM,
                "pdf_metadata",
            )

        component = self._detect_component(text)
        if component is not ExamComponent.UNKNOWN:
            return self._field(
                component.value,
                MetadataConfidence.MEDIUM,
                "document_text",
            )

        return self._unknown_field()

    def _extract_document_type(
        self,
        source: Mapping[str, Any],
        pdf: Mapping[str, Any],
        text: str,
    ) -> ExtractedField:
        value = self._first_value(
            source,
            ("document_type", "type", "tipo_documento"),
        )
        if value:
            return self._field(
                str(value),
                MetadataConfidence.HIGH,
                "ingestion_event",
            )

        title = self._first_value(pdf, ("title",))
        if title:
            normalized = self._normalize_text(str(title))
            for label, document_type in self.DOCUMENT_TYPE_VALUES.items():
                if label in normalized:
                    return self._field(
                        document_type,
                        MetadataConfidence.MEDIUM,
                        "pdf_metadata",
                    )

        normalized_text = self._normalize_text(text[:5000])
        for label, document_type in self.DOCUMENT_TYPE_VALUES.items():
            if label in normalized_text:
                return self._field(
                    document_type,
                    MetadataConfidence.LOW,
                    "document_text",
                )

        return self._unknown_field()

    def _extract_competencies(
        self,
        text: str,
    ) -> tuple[ExtractedCompetency, ...]:
        competencies: dict[str, ExtractedCompetency] = {}

        for pattern in self.COMPETENCY_PATTERNS:
            for match in pattern.finditer(text):
                identifier = match.group(1)
                description = self._clean_value(match.group(2))

                if not description:
                    continue

                key = self._normalize_text(description)
                if key in competencies:
                    continue

                competencies[key] = ExtractedCompetency(
                    description=description,
                    identifier=identifier,
                    source="document_text",
                    confidence=MetadataConfidence.MEDIUM,
                )

        return tuple(competencies.values())

    def _extract_question_metadata(
        self,
        segmented_questions: SegmentedQuestions | None,
        text: str,
    ) -> tuple[QuestionMetadata, ...]:
        if segmented_questions is None:
            return ()

        segments = getattr(segmented_questions, "questions", ())
        if not segments:
            segments = getattr(segmented_questions, "segments", ())

        if not segments:
            return ()

        section_positions = self._find_component_positions(text)
        result: list[QuestionMetadata] = []

        for segment in segments:
            question_number = getattr(segment, "number", None)
            if question_number is None:
                question_number = getattr(segment, "question_number", None)

            if not isinstance(question_number, int):
                continue

            question_text = str(
                getattr(segment, "text", "")
                or getattr(segment, "statement", "")
                or ""
            )

            component = self._component_for_question(
                question_text,
                section_positions,
            )

            result.append(
                QuestionMetadata(
                    question_number=question_number,
                    component=component,
                    competencies=self._extract_competencies(question_text),
                )
            )

        return tuple(result)

    def _find_component_positions(
        self,
        text: str,
    ) -> list[tuple[int, ExamComponent]]:
        positions: list[tuple[int, ExamComponent]] = []

        for pattern in self.GENERAL_FORMATION_PATTERNS:
            positions.extend(
                (match.start(), ExamComponent.GENERAL_FORMATION)
                for match in pattern.finditer(text)
            )

        for pattern in self.SPECIFIC_COMPONENT_PATTERNS:
            positions.extend(
                (match.start(), ExamComponent.SPECIFIC_COMPONENT)
                for match in pattern.finditer(text)
            )

        positions.sort(key=lambda item: item[0])
        return positions

    def _component_for_question(
        self,
        question_text: str,
        section_positions: Sequence[tuple[int, ExamComponent]],
    ) -> ExamComponent:
        normalized_question = self._normalize_text(question_text)

        if any(
            self._normalize_text(pattern.pattern.replace(r"\b", "")) in normalized_question
            for pattern in ()
        ):
            return ExamComponent.UNKNOWN

        if any(pattern.search(question_text) for pattern in self.GENERAL_FORMATION_PATTERNS):
            return ExamComponent.GENERAL_FORMATION

        if any(pattern.search(question_text) for pattern in self.SPECIFIC_COMPONENT_PATTERNS):
            return ExamComponent.SPECIFIC_COMPONENT

        # A associação por posição exige que o segmento possua um intervalo
        # de texto confiável. Sem essa informação, não se atribui FG/CE.
        return ExamComponent.UNKNOWN

    @staticmethod
    def _detect_component(text: str) -> ExamComponent:
        general = any(
            pattern.search(text)
            for pattern in MetadataExtractor.GENERAL_FORMATION_PATTERNS
        )
        specific = any(
            pattern.search(text)
            for pattern in MetadataExtractor.SPECIFIC_COMPONENT_PATTERNS
        )

        if general and not specific:
            return ExamComponent.GENERAL_FORMATION

        if specific and not general:
            return ExamComponent.SPECIFIC_COMPONENT

        return ExamComponent.UNKNOWN

    @staticmethod
    def _parse_component(value: Any) -> ExamComponent:
        if value is None:
            return ExamComponent.UNKNOWN

        normalized = MetadataExtractor._normalize_text(str(value)).upper()

        if normalized in {"FG", "FORMACAO GERAL", "GENERAL FORMATION"}:
            return ExamComponent.GENERAL_FORMATION

        if normalized in {
            "CE",
            "COMPONENTE ESPECIFICO",
            "SPECIFIC COMPONENT",
        }:
            return ExamComponent.SPECIFIC_COMPONENT

        return ExamComponent.UNKNOWN

    @staticmethod
    def _parse_year(value: Any) -> int | None:
        if value is None:
            return None

        match = re.search(r"\b(20\d{2})\b", str(value))
        if not match:
            return None

        year = int(match.group(1))
        return year if 2000 <= year <= 2099 else None

    @staticmethod
    def _normalize_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            return {}

        return {
            str(key).strip().lower(): item
            for key, item in value.items()
            if key is not None
        }

    @staticmethod
    def _first_value(
        metadata: Mapping[str, Any],
        keys: Sequence[str],
    ) -> Any:
        for key in keys:
            value = metadata.get(key.lower())
            if value is not None and str(value).strip():
                return value

        return None

    @staticmethod
    def _first_pattern_value(
        patterns: Sequence[re.Pattern[str]],
        text: str,
    ) -> str | None:
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                value = MetadataExtractor._clean_value(match.group(1))
                if value:
                    return value

        return None

    @staticmethod
    def _clean_value(value: str) -> str:
        cleaned = re.sub(r"\s+", " ", value).strip(" \t-:;,.")
        return cleaned or ""

    @staticmethod
    def _field(
        value: str | int,
        confidence: MetadataConfidence,
        source: str,
    ) -> ExtractedField:
        if isinstance(value, str):
            value = MetadataExtractor._clean_value(value)

        if value == "":
            return MetadataExtractor._unknown_field()

        return ExtractedField(
            value=value,
            confidence=confidence,
            source=source,
        )

    @staticmethod
    def _unknown_field() -> ExtractedField:
        return ExtractedField(
            value=None,
            confidence=MetadataConfidence.UNKNOWN,
            source=None,
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        return "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        ).lower()

    @staticmethod
    def _extract_text_from_pages(pages: Sequence[Any]) -> str:
        return "\n".join(
            str(getattr(page, "text", "") or "")
            for page in pages
        )
