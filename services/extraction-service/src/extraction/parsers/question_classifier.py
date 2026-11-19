from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum

from extraction.parsers.question_segmenter import (
    AnswerStatus,
    QuestionSegment,
    QuestionType,
    SegmentedQuestions,
)


logger = logging.getLogger(__name__)


class QuestionClassificationError(Exception):
    """Erro durante a classificação das questões"""


class ClassificationConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class QuestionClassification:
    question_number: int
    question_type: QuestionType
    answer_status: AnswerStatus
    confidence: ClassificationConfidence
    classification_reasons: tuple[str, ...]
    has_alternatives: bool
    alternative_count: int

    def __post_init__(self) -> None:
        if self.question_number <= 0:
            raise ValueError("O número da questão precisa ser positivo.")

        if self.alternative_count < 0:
            raise ValueError("A quantidade de alternativas não pode ser negativa.")

        if self.alternative_count != int(self.has_alternatives) and (
            not self.has_alternatives or self.alternative_count == 0
        ):
            raise ValueError("A quantidade de alternativas é inconsistente.")


@dataclass(frozen=True, slots=True)
class ClassifiedQuestion:
    question: QuestionSegment
    classification: QuestionClassification


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    storage_key: str
    checksum: str
    questions: tuple[ClassifiedQuestion, ...]

    @property
    def total_questions(self) -> int:
        return len(self.questions)

    @property
    def objective_count(self) -> int:
        return sum(
            item.classification.question_type == QuestionType.OBJECTIVE
            for item in self.questions
        )

    @property
    def discursive_count(self) -> int:
        return sum(
            item.classification.question_type == QuestionType.DISCURSIVE
            for item in self.questions
        )

    @property
    def annulled_count(self) -> int:
        return sum(
            item.classification.answer_status == AnswerStatus.ANNULLED
            for item in self.questions
        )

    @property
    def unknown_count(self) -> int:
        return sum(
            item.classification.question_type == QuestionType.UNKNOWN
            for item in self.questions
        )


class QuestionClassifier:

    DISCURSIVE_PATTERNS = (
        re.compile(
            r"\b(?:redija|elabore|discorra|justifique|explique|"
            r"descreva|analise|argumente|comente|apresente)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:em\s+sua\s+resposta|"
            r"fundamente\s+sua\s+resposta|"
            r"apresente\s+uma\s+proposta)\b",
            re.IGNORECASE,
        ),
    )

    ANNULLED_PATTERNS = (
        re.compile(r"\b(?:quest[aã]o)\s+anulada\b", re.IGNORECASE),
        re.compile(r"\b(?:item)\s+anulado\b", re.IGNORECASE),
        re.compile(r"\b(?:anulada|anulado)\s+(?:pela\s+banca|oficialmente)\b", re.IGNORECASE),
    )

    def __init__(
        self,
        minimum_objective_alternatives: int = 2,
        maximum_objective_alternatives: int = 5,
    ) -> None:
        if not 2 <= minimum_objective_alternatives <= 5:
            raise ValueError(
                "O mínimo de alternativas precisa estar entre 2 e 5."
            )

        if not minimum_objective_alternatives <= maximum_objective_alternatives <= 5:
            raise ValueError(
                "O máximo de alternativas precisa ser compatível com o mínimo."
            )

        self._minimum_objective_alternatives = (
            minimum_objective_alternatives
        )
        self._maximum_objective_alternatives = (
            maximum_objective_alternatives
        )

    def classify(
        self,
        segmented_questions: SegmentedQuestions,
    ) -> ClassificationResult:
        if not isinstance(segmented_questions, SegmentedQuestions):
            raise TypeError(
                "O classificador espera receber SegmentedQuestions."
            )

        if not segmented_questions.questions:
            raise QuestionClassificationError(
                "Não existem questões para classificar."
            )

        classified_questions: list[ClassifiedQuestion] = []

        try:
            for question in segmented_questions.questions:
                classification = self._classificar_questao(question)

                classified_questions.append(
                    ClassifiedQuestion(
                        question=question,
                        classification=classification,
                    )
                )

            result = ClassificationResult(
                storage_key=segmented_questions.storage_key,
                checksum=segmented_questions.checksum,
                questions=tuple(classified_questions),
            )

            logger.info(
                "Classificação concluída. storage_key=%s total=%s "
                "objective=%s discursive=%s annulled=%s unknown=%s",
                result.storage_key,
                result.total_questions,
                result.objective_count,
                result.discursive_count,
                result.annulled_count,
                result.unknown_count,
            )

            return result

        except QuestionClassificationError:
            raise

        except Exception as exc:
            logger.exception(
                "Falha na classificação das questões. storage_key=%s",
                segmented_questions.storage_key,
            )

            raise QuestionClassificationError(
                "Não foi possível classificar as questões."
            ) from exc

    def _classificar_questao(
        self,
        question: QuestionSegment,
    ) -> QuestionClassification:
        reasons: list[str] = []

        alternative_count = len(question.alternatives)

        has_alternatives = (
            self._minimum_objective_alternatives
            <= alternative_count
            <= self._maximum_objective_alternatives
        )

        answer_status = question.answer_status

        # Anulação só é confirmada por informação explícita.
        if answer_status == AnswerStatus.ANNULLED:
            reasons.append("Gabarito identifica explicitamente a questão como anulada.")

            question_type = (
                QuestionType.OBJECTIVE
                if has_alternatives
                else QuestionType.UNKNOWN
            )

            confidence = ClassificationConfidence.HIGH

        elif self._possui_indicacao_anulacao(question):
            answer_status = AnswerStatus.ANNULLED
            reasons.append("Texto do documento indica anulação explícita.")

            question_type = (
                QuestionType.OBJECTIVE
                if has_alternatives
                else QuestionType.UNKNOWN
            )

            confidence = ClassificationConfidence.HIGH

        elif has_alternatives:
            question_type = QuestionType.OBJECTIVE
            reasons.append(
                f"Foram identificadas {alternative_count} alternativas."
            )

            confidence = ClassificationConfidence.HIGH

        elif question.question_type == QuestionType.DISCURSIVE:
            question_type = QuestionType.DISCURSIVE
            reasons.append(
                "Segmentador identificou estrutura discursiva."
            )

            confidence = ClassificationConfidence.MEDIUM

        elif self._possui_indicacao_discursiva(question):
            question_type = QuestionType.DISCURSIVE
            reasons.append(
                "Enunciado apresenta instruções características de resposta discursiva."
            )

            confidence = ClassificationConfidence.MEDIUM

        else:
            question_type = QuestionType.UNKNOWN
            reasons.append(
                "Não existem evidências estruturais suficientes para classificação."
            )

            confidence = ClassificationConfidence.LOW

        return QuestionClassification(
            question_number=question.question_number,
            question_type=question_type,
            answer_status=answer_status,
            confidence=confidence,
            classification_reasons=tuple(reasons),
            has_alternatives=has_alternatives,
            alternative_count=alternative_count,
        )

    def _possui_indicacao_anulacao(
        self,
        question: QuestionSegment,
    ) -> bool:
        text = question.raw_text or question.statement

        return any(
            pattern.search(text)
            for pattern in self.ANNULLED_PATTERNS
        )

    def _possui_indicacao_discursiva(
        self,
        question: QuestionSegment,
    ) -> bool:
        text = question.statement

        return any(
            pattern.search(text)
            for pattern in self.DISCURSIVE_PATTERNS
        )
