from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence


class TableConversionError(Exception):
    """Erro durante a conversão de tabelas para Markdown."""


class TableConversionStatus(str, Enum):
    CONVERTED = "converted"
    NORMALIZED = "normalized"
    EMPTY = "empty"


@dataclass(frozen=True)
class TableCell:
    value: str
    row_span: int = 1
    column_span: int = 1

    def __post_init__(self) -> None:
        if self.row_span < 1:
            raise ValueError("row_span deve ser maior ou igual a 1.")

        if self.column_span < 1:
            raise ValueError("column_span deve ser maior ou igual a 1.")


@dataclass(frozen=True)
class TableRow:
    cells: tuple[TableCell, ...]
    is_header: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.cells, tuple):
            object.__setattr__(self, "cells", tuple(self.cells))


@dataclass(frozen=True)
class TableData:
    rows: tuple[TableRow, ...]
    title: str | None = None
    headers: tuple[str, ...] = ()
    page_number: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.rows, tuple):
            object.__setattr__(self, "rows", tuple(self.rows))

        if not isinstance(self.headers, tuple):
            object.__setattr__(self, "headers", tuple(self.headers))

        if self.page_number is not None and self.page_number < 1:
            raise ValueError("page_number deve ser maior ou igual a 1.")


@dataclass(frozen=True)
class TableConversionResult:
    markdown: str
    status: TableConversionStatus
    row_count: int
    column_count: int
    title: str | None = None
    page_number: int | None = None


class TableConverter:

    def convert(
        self,
        table: TableData | Sequence[Sequence[Any]],
        headers: Sequence[str] | None = None,
        title: str | None = None,
        page_number: int | None = None,
    ) -> TableConversionResult:

        normalized_table = self._normalize_input(
            table=table,
            headers=headers,
            title=title,
            page_number=page_number,
        )

        if not normalized_table.rows:
            return TableConversionResult(
                markdown="",
                status=TableConversionStatus.EMPTY,
                row_count=0,
                column_count=0,
                title=normalized_table.title,
                page_number=normalized_table.page_number,
            )

        matrix = self._build_matrix(normalized_table)
        if not matrix:
            return TableConversionResult(
                markdown="",
                status=TableConversionStatus.EMPTY,
                row_count=0,
                column_count=0,
                title=normalized_table.title,
                page_number=normalized_table.page_number,
            )

        markdown = self._render_markdown(matrix)

        if normalized_table.title:
            markdown = f"**{self._escape_text(normalized_table.title)}**\n\n{markdown}"

        return TableConversionResult(
            markdown=markdown,
            status=TableConversionStatus.CONVERTED,
            row_count=len(matrix),
            column_count=len(matrix[0]),
            title=normalized_table.title,
            page_number=normalized_table.page_number,
        )

    def convert_many(
        self,
        tables: Iterable[TableData | Sequence[Sequence[Any]]],
    ) -> tuple[TableConversionResult, ...]:
        """Converte uma coleção de tabelas."""
        if tables is None:
            raise TableConversionError("A coleção de tabelas não foi informada.")

        return tuple(self.convert(table) for table in tables)

    def _normalize_input(
        self,
        table: TableData | Sequence[Sequence[Any]],
        headers: Sequence[str] | None,
        title: str | None,
        page_number: int | None,
    ) -> TableData:
        if isinstance(table, TableData):
            if headers is not None or title is not None or page_number is not None:
                raise TableConversionError(
                    "Não informe metadados adicionais quando a entrada já for TableData."
                )
            return table

        if isinstance(table, (str, bytes)) or not isinstance(table, Sequence):
            raise TableConversionError(
                "A tabela deve ser TableData ou uma sequência de linhas."
            )

        rows: list[TableRow] = []

        for row in table:
            if isinstance(row, (str, bytes)) or not isinstance(row, Sequence):
                raise TableConversionError(
                    "Cada linha deve ser uma sequência de células."
                )

            rows.append(
                TableRow(
                    cells=tuple(
                        self._normalize_cell(cell)
                        for cell in row
                    )
                )
            )

        normalized_headers = tuple(
            self._cell_value(header)
            for header in headers
        ) if headers is not None else ()

        return TableData(
            rows=tuple(rows),
            headers=normalized_headers,
            title=title,
            page_number=page_number,
        )

    def _build_matrix(self, table: TableData) -> list[list[str]]:
        matrix = [
            [cell.value for cell in row.cells]
            for row in table.rows
        ]

        if not matrix:
            return []

        max_columns = max(
            len(row)
            for row in matrix
        )

        if max_columns == 0 and not table.headers:
            return []

        if table.headers:
            header_row = list(table.headers)
            max_columns = max(max_columns, len(header_row))
            matrix.insert(0, header_row)

        matrix = [
            row + [""] * (max_columns - len(row))
            for row in matrix
        ]

        return matrix

    def _render_markdown(self, matrix: list[list[str]]) -> str:
        if not matrix:
            return ""

        column_count = len(matrix[0])

        if column_count == 0:
            return ""

        header = matrix[0]
        body = matrix[1:]

        header_line = self._render_row(header)
        separator_line = "| " + " | ".join("---" for _ in range(column_count)) + " |"

        lines = [header_line, separator_line]
        lines.extend(
            self._render_row(row)
            for row in body
        )

        return "\n".join(lines)

    def _render_row(self, cells: Sequence[str]) -> str:
        escaped_cells = [
            self._escape_cell(cell)
            for cell in cells
        ]
        return "| " + " | ".join(escaped_cells) + " |"

    @staticmethod
    def _normalize_cell(value: Any) -> TableCell:
        if isinstance(value, TableCell):
            return value

        return TableCell(
            value=TableConverter._cell_value(value)
        )

    @staticmethod
    def _cell_value(value: Any) -> str:
        if value is None:
            return ""

        if isinstance(value, float):
            return str(value)

        return str(value).strip()

    @staticmethod
    def _escape_cell(value: str) -> str:
        escaped = value.replace("\\", "\\\\")
        escaped = escaped.replace("|", r"\|")
        escaped = re.sub(r"\r\n|\r|\n", "<br>", escaped)
        return escaped.strip()

    @staticmethod
    def _escape_text(value: str) -> str:
        return value.replace("\\", "\\\\").replace("|", r"\|")
