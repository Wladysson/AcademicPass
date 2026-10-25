from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum

from extraction.parsers.pdf_parser import ParsedPdf, PdfPage


logger = logging.getLogger(__name__)


class QuestionSegmentationError(Exception):
    """Erro durante a segmentação das questões"""


class QuestionType(str, Enum):
    OBJECTIVE = "objective"
    DISCURSIVE = "discursive"
    UNKNOWN = "unknown"


class AnswerStatus(str, Enum):
    CORRECT = "correct"
    ANNULLED = "annulled"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class QuestionAlternative:
    label: str
    text: str

    def __post_init__(self) -> None:
        if self.label not in {"A", "B", "C", "D", "E"}:
            raise ValueError("Rótulo de alternativa inválido.")

        if not self.text.strip():
            raise ValueError("O texto da alternativa não pode estar vazio.")


@dataclass(frozen=True, slots=True)
class QuestionSegment:
    question_number: int
    question_type: QuestionType
    statement: str
    base_text: str | None = None
    alternatives: tuple[QuestionAlternative, ...] = ()
    answer: str | None = None
    answer_status: AnswerStatus = AnswerStatus.UNAVAILABLE
    start_page: int = 1
    end_page: int = 1
    source_pages: tuple[int, ...] = ()
    raw_text: str = ""

    def __post_init__(self) -> None:
        if self.question_number <= 0:
            raise ValueError("O número da questão precisa ser positivo.")

        if not self.statement.strip():
            raise ValueError("O enunciado da questão é obrigatório.")

        if self.start_page <= 0 or self.end_page < self.start_page:
            raise ValueError("Intervalo de páginas inválido.")

        if self.answer is not None and self.answer not in {
            "A", "B", "C", "D", "E"
        }:
            raise ValueError("Gabarito inválido.")

        if self.answer_status == AnswerStatus.ANNULLED:
            if self.answer is not None:
                raise ValueError(
                    "Uma questão anulada não pode possuir alternativa correta."
                )


@dataclass(frozen=True, slots=True)
class SegmentedQuestions:
    storage_key: str
    checksum: str
    questions: tuple[QuestionSegment, ...]
    unsegmented_text: str = field(default="")

    @property
    def total_questions(self) -> int:
        return len(self.questions)


class QuestionSegmenter:

    QUESTION_PATTERN = re.compile(
        r"(?im)^[ \t]*(?:QUESTÃO|QUESTAO|QUESTION)"
        r"[ \t]*(?:N[º°.]?[ \t]*)?"
        r"(?P<number>\d{1,3})"
        r"[ \t]*(?:[-.:)]\s*|$)"
    )

    ALTERNATIVE_PATTERN = re.compile(
        r"(?im)^[ \t]*(?P<label>[A-E])"
        r"[ \t]*[).\-:][ \t]+(?P<text>.+)"
    )

    ANSWER_PATTERN = re.compile(
        r"(?im)^[ \t]*(?:GABARITO|RESPOSTA)"
        r"[ \t]*(?:DA[ \t]+QUEST[ÃA]O)?"
        r"[ \t]*(?P<number>\d{1,3})?"
        r"[ \t]*[:\-]?[ \t]*(?P<answer>[A-E]|ANULADA|ANULADO)"
        r"[ \t]*$"
    )

    SHARED_TEXT_PATTERN = re.compile(
        r"(?im)^[ \t]*(?:"
        r"TEXTO(?:[ \t]+BASE)?|"
        r"LEIA[ \t]+O[ \t]+TEXTO|"
        r"COM[ \t]+BASE[ \t]+NO[ \t]+TEXTO|"
        r"ANALISE[ \t]+A[ \t]+IMAGEM"
        r")[ \t]*[:\-]?[ \t]*$"
    )

    def __init__(
        self,
        minimum_statement_length: int = 10,
        minimum_alternatives: int = 2,
        maximum_question_number: int = 200,
    ) -> None:
        if minimum_statement_length <= 0:
            raise ValueError(
                "O tamanho mínimo do enunciado precisa ser positivo."
            )

        if not 2 <= minimum_alternatives <= 5:
            raise ValueError(
                "O mínimo de alternativas precisa estar entre 2 e 5."
            )

        if maximum_question_number <= 0:
            raise ValueError(
                "O limite máximo de questões precisa ser positivo."
            )

        self._minimum_statement_length = minimum_statement_length
        self._minimum_alternatives = minimum_alternatives
        self._maximum_question_number = maximum_question_number

    def segment(self, parsed_pdf: ParsedPdf) -> SegmentedQuestions:
        if not isinstance(parsed_pdf, ParsedPdf):
            raise TypeError(
                "O segmentador espera receber uma instância de ParsedPdf."
            )

        if not parsed_pdf.pages:
            raise QuestionSegmentationError(
                "O documento não possui páginas para segmentação."
            )

        try:
            page_texts = [
                (page.page_number, page.text)
                for page in parsed_pdf.pages
            ]

            full_text = "\n".join(
                text for _, text in page_texts
            )

            if not full_text.strip():
                raise QuestionSegmentationError(
                    "O documento não possui texto extraível."
                )

            answer_key = self._extrair_gabarito(full_text)

            question_matches = list(
                self.QUESTION_PATTERN.finditer(full_text)
            )

            candidates = self._validar_marcadores(
                question_matches,
                page_texts,
            )

            if not candidates:
                raise QuestionSegmentationError(
                    "Não foram encontrados marcadores de questões válidos."
                )

            segments: list[QuestionSegment] = []

            for index, candidate in enumerate(candidates):
                start = candidate["start"]
                end = (
                    candidates[index + 1]["start"]
                    if index + 1 < len(candidates)
                    else len(full_text)
                )

                raw_text = full_text[start:end].strip()

                if not raw_text:
                    continue

                question_number = candidate["number"]

                segment = self._segmentar_questao(
                    question_number=question_number,
                    raw_text=raw_text,
                    start_page=candidate["page"],
                    end_page=self._identificar_pagina_final(
                        end,
                        page_texts,
                        candidate["page"],
                    ),
                    answer=answer_key.get(question_number),
                )

                if segment is not None:
                    segments.append(segment)

            if not segments:
                raise QuestionSegmentationError(
                    "Nenhuma questão pôde ser segmentada."
                )

            logger.info(
                "Segmentação concluída. storage_key=%s total_questions=%s",
                parsed_pdf.storage_key,
                len(segments),
            )

            return SegmentedQuestions(
                storage_key=parsed_pdf.storage_key,
                checksum=parsed_pdf.checksum,
                questions=tuple(segments),
                unsegmented_text=self._extrair_texto_nao_segmentado(
                    full_text,
                    candidates,
                ),
            )

        except QuestionSegmentationError:
            raise

        except Exception as exc:
            logger.exception(
                "Falha na segmentação do documento. storage_key=%s",
                parsed_pdf.storage_key,
            )

            raise QuestionSegmentationError(
                "Não foi possível segmentar as questões do documento."
            ) from exc

    def _validar_marcadores(
        self,
        matches: list[re.Match[str]],
        page_texts: list[tuple[int, str]],
    ) -> list[dict[str, int]]:
        candidates: list[dict[str, int]] = []
        previous_number = 0

        offsets: list[tuple[int, int]] = []
        current_offset = 0

        for page_number, text in page_texts:
            offsets.append((current_offset, page_number))
            current_offset += len(text) + 1

        for match in matches:
            number = int(match.group("number"))

            if not 1 <= number <= self._maximum_question_number:
                continue

            if number <= previous_number:
                continue

            if number - previous_number > 3 and previous_number != 0:
                continue

            page_number = self._identificar_pagina_por_offset(
                match.start(),
                offsets,
            )

            candidates.append(
                {
                    "number": number,
                    "start": match.start(),
                    "page": page_number,
                }
            )

            previous_number = number

        return candidates

    def _segmentar_questao(
        self,
        question_number: int,
        raw_text: str,
        start_page: int,
        end_page: int,
        answer: tuple[str | None, AnswerStatus] | None,
    ) -> QuestionSegment | None:
        lines = [
            line.strip()
            for line in raw_text.splitlines()
            if line.strip()
        ]

        if not lines:
            return None

        if self.QUESTION_PATTERN.match(lines[0]):
            lines = lines[1:]

        alternative_indexes = [
            index
            for index, line in enumerate(lines)
            if self.ALTERNATIVE_PATTERN.match(line)
        ]

        alternatives: list[QuestionAlternative] = []

        for index, alternative_index in enumerate(alternative_indexes):
            match = self.ALTERNATIVE_PATTERN.match(
                lines[alternative_index]
            )

            if match is None:
                continue

            next_index = (
                alternative_indexes[index + 1]
                if index + 1 < len(alternative_indexes)
                else len(lines)
            )

            alternative_text = " ".join(
                lines[alternative_index + 1:next_index]
            )

            complete_text = " ".join(
                part
                for part in (
                    match.group("text"),
                    alternative_text,
                )
                if part
            ).strip()

            alternatives.append(
                QuestionAlternative(
                    label=match.group("label").upper(),
                    text=complete_text,
                )
            )

        if len(alternatives) >= self._minimum_alternatives:
            first_alternative = alternative_indexes[0]

            statement_lines = lines[:first_alternative]

            question_type = QuestionType.OBJECTIVE

        else:
            statement_lines = lines
            question_type = QuestionType.DISCURSIVE

        statement, base_text = self._separar_texto_base(
            statement_lines
        )

        if len(statement.strip()) < self._minimum_statement_length:
            logger.warning(
                "Questão descartada por enunciado insuficiente. question=%s",
                question_number,
            )
            return None

        answer_value = answer[0] if answer else None
        answer_status = (
            answer[1]
            if answer
            else AnswerStatus.UNAVAILABLE
        )

        return QuestionSegment(
            question_number=question_number,
            question_type=question_type,
            statement=statement,
            base_text=base_text,
            alternatives=tuple(alternatives),
            answer=answer_value,
            answer_status=answer_status,
            start_page=start_page,
            end_page=end_page,
            source_pages=tuple(
                range(start_page, end_page + 1)
            ),
            raw_text=raw_text,
        )

    def _extrair_gabarito(
        self,
        full_text: str,
    ) -> dict[int, tuple[str | None, AnswerStatus]]:
        answer_key: dict[int, tuple[str | None, AnswerStatus]] = {}

        for match in self.ANSWER_PATTERN.finditer(full_text):
            number = match.group("number")

            if number is None:
                continue

            question_number = int(number)
            answer = match.group("answer").upper()

            if answer in {"ANULADA", "ANULADO"}:
                answer_key[question_number] = (
                    None,
                    AnswerStatus.ANNULLED,
                )
            else:
                answer_key[question_number] = (
                    answer,
                    AnswerStatus.CORRECT,
                )

        return answer_key

    def _separar_texto_base(
        self,
        lines: list[str],
    ) -> tuple[str, str | None]:
        shared_text_indexes = [
            index
            for index, line in enumerate(lines)
            if self.SHARED_TEXT_PATTERN.match(line)
        ]

        if not shared_text_indexes:
            return "\n".join(lines).strip(), None

        first_index = shared_text_indexes[0]

        statement = "\n".join(lines[first_index:]).strip()
        base_text = "\n".join(lines[:first_index]).strip()

        if not base_text:
            return statement, None

        return statement, base_text

    @staticmethod
    def _identificar_pagina_por_offset(
        offset: int,
        page_offsets: list[tuple[int, int]],
    ) -> int:
        page_number = 1

        for page_offset, number in page_offsets:
            if page_offset > offset:
                break

            page_number = number

        return page_number

    def _identificar_pagina_final(
        self,
        end_offset: int,
        page_texts: list[tuple[int, str]],
        default_page: int,
    ) -> int:
        offsets: list[tuple[int, int]] = []
        current_offset = 0

        for page_number, text in page_texts:
            offsets.append((current_offset, page_number))
            current_offset += len(text) + 1

        if end_offset <= 0:
            return default_page

        return self._identificar_pagina_por_offset(
            end_offset - 1,
            offsets,
        )

    @staticmethod
    def _extrair_texto_nao_segmentado(
        full_text: str,
        candidates: list[dict[str, int]],
    ) -> str:
        if not candidates:
            return full_text

        first_question_start = candidates[0]["start"]

        return full_text[:first_question_start].strip()
