from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pymupdf

from extraction.storage.pdf_reader import PdfDocument


logger = logging.getLogger(__name__)


class PdfParserError(Exception):
    """Erro durante a interpretação de documentos PDF"""


class PdfPasswordError(PdfParserError):
    """Documento PDF protegido por senha"""


@dataclass(frozen=True, slots=True)
class PdfTextBlock:
    page_number: int
    block_number: int
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    width: float
    height: float
    block_type: int

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise ValueError("O número da página deve começar em 1.")

        if self.block_number < 0:
            raise ValueError("O número do bloco não pode ser negativo.")


@dataclass(frozen=True, slots=True)
class PdfPage:
    page_number: int
    width: float
    height: float
    rotation: int
    text: str
    blocks: tuple[PdfTextBlock, ...]
    has_images: bool = False

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise ValueError("O número da página deve começar em 1.")

        if self.width <= 0 or self.height <= 0:
            raise ValueError("As dimensões da página precisam ser positivas.")


@dataclass(frozen=True, slots=True)
class ParsedPdf:
    storage_key: str
    file_name: str
    checksum: str
    size_bytes: int
    page_count: int
    full_text: str
    pages: tuple[PdfPage, ...]
    metadata: dict[str, Any] = field(default_factory=dict)
    encrypted: bool = False
    has_extractable_text: bool = False

    def __post_init__(self) -> None:
        if self.page_count <= 0:
            raise ValueError("O PDF precisa possuir pelo menos uma página.")

        if self.page_count != len(self.pages):
            raise ValueError(
                "A quantidade de páginas não corresponde aos dados extraídos."
            )


class PdfParser:

    def __init__(
        self,
        max_pages: int = 1000,
        min_text_characters: int = 1,
        preserve_whitespace: bool = True,
        sort_blocks: bool = True,
        extract_images_info: bool = True,
    ) -> None:
        if max_pages <= 0:
            raise ValueError("O limite de páginas precisa ser positivo.")

        if min_text_characters < 0:
            raise ValueError(
                "O limite mínimo de caracteres não pode ser negativo."
            )

        self._max_pages = max_pages
        self._min_text_characters = min_text_characters
        self._preserve_whitespace = preserve_whitespace
        self._sort_blocks = sort_blocks
        self._extract_images_info = extract_images_info

    def parse(self, document: PdfDocument) -> ParsedPdf:
        if not isinstance(document, PdfDocument):
            raise TypeError(
                "O parser espera receber uma instância de PdfDocument."
            )

        try:
            with pymupdf.open(
                stream=document.content,
                filetype="pdf",
            ) as pdf:
                if pdf.is_encrypted:
                    raise PdfPasswordError(
                        "O documento PDF está protegido por senha."
                    )

                if pdf.page_count <= 0:
                    raise PdfParserError(
                        "O documento PDF não possui páginas."
                    )

                if pdf.page_count > self._max_pages:
                    raise PdfParserError(
                        "O documento excede o limite máximo de páginas."
                    )

                pages = tuple(
                    self._extrair_pagina(pdf.load_page(index), index + 1)
                    for index in range(pdf.page_count)
                )

                full_text = "\n\n".join(
                    page.text for page in pages if page.text
                )

                extracted_characters = len(full_text.strip())

                return ParsedPdf(
                    storage_key=document.storage_key,
                    file_name=document.file_name,
                    checksum=document.checksum,
                    size_bytes=document.size_bytes,
                    page_count=pdf.page_count,
                    full_text=full_text,
                    pages=pages,
                    metadata=self._extrair_metadados(pdf),
                    encrypted=pdf.is_encrypted,
                    has_extractable_text=(
                        extracted_characters >= self._min_text_characters
                    ),
                )

        except PdfPasswordError:
            raise

        except PdfParserError:
            raise

        except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
            logger.exception(
                "Falha ao interpretar documento PDF. storage_key=%s",
                document.storage_key,
            )

            raise PdfParserError(
                "Não foi possível interpretar o conteúdo do documento PDF."
            ) from exc

        except Exception as exc:
            logger.exception(
                "Erro inesperado durante a extração do PDF. storage_key=%s",
                document.storage_key,
            )

            raise PdfParserError(
                "Ocorreu um erro inesperado durante a interpretação do PDF."
            ) from exc

    def _extrair_pagina(
        self,
        page: pymupdf.Page,
        page_number: int,
    ) -> PdfPage:
        try:
            raw_blocks = page.get_text(
                "blocks",
                sort=self._sort_blocks,
            )

            blocks = tuple(
                self._converter_bloco(block, page_number, index)
                for index, block in enumerate(raw_blocks)
                if len(block) >= 7 and block[6].strip()
            )

            text = page.get_text(
                "text",
                sort=self._sort_blocks,
            )

            if not self._preserve_whitespace:
                text = self._normalizar_texto(text)

            page_rect = page.rect

            has_images = (
                bool(page.get_images(full=True))
                if self._extract_images_info
                else False
            )

            return PdfPage(
                page_number=page_number,
                width=page_rect.width,
                height=page_rect.height,
                rotation=page.rotation,
                text=text,
                blocks=blocks,
                has_images=has_images,
            )

        except Exception as exc:
            raise PdfParserError(
                f"Falha ao extrair conteúdo da página {page_number}."
            ) from exc

    @staticmethod
    def _converter_bloco(
        block: tuple[Any, ...],
        page_number: int,
        block_number: int,
    ) -> PdfTextBlock:
        x0, y0, x1, y1, text, _, block_type = block[:7]

        return PdfTextBlock(
            page_number=page_number,
            block_number=block_number,
            text=text.strip(),
            x0=float(x0),
            y0=float(y0),
            x1=float(x1),
            y1=float(y1),
            width=float(x1 - x0),
            height=float(y1 - y0),
            block_type=int(block_type),
        )

    @staticmethod
    def _extrair_metadados(
        pdf: pymupdf.Document,
    ) -> dict[str, Any]:
        metadata = pdf.metadata or {}

        return {
            "title": metadata.get("title"),
            "author": metadata.get("author"),
            "subject": metadata.get("subject"),
            "keywords": metadata.get("keywords"),
            "creator": metadata.get("creator"),
            "producer": metadata.get("producer"),
            "creation_date": metadata.get("creationDate"),
            "modification_date": metadata.get("modDate"),
            "format": metadata.get("format"),
        }

    @staticmethod
    def _normalizar_texto(text: str) -> str:
        lines = [
            " ".join(line.split())
            for line in text.splitlines()
        ]

        return "\n".join(
            line for line in lines if line
        )
