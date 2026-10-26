from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class FormulaConversionError(Exception):
    """Erro durante a conversão de expressões matemáticas"""


class ConversionStatus(str, Enum):
    CONVERTED = "converted"
    ALREADY_LATEX = "already_latex"
    UNCHANGED = "unchanged"
    FAILED = "failed"


class FormulaFormat(str, Enum):
    INLINE = "inline"
    DISPLAY = "display"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FormulaExpression:
    original: str
    latex: str
    status: ConversionStatus
    format: FormulaFormat = FormulaFormat.UNKNOWN
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not self.original.strip():
            raise ValueError("A expressão original não pode ser vazia.")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("A confiança deve estar entre 0 e 1.")


@dataclass(frozen=True)
class FormulaConversionResult:
    original_text: str
    converted_text: str
    formulas: tuple[FormulaExpression, ...]

    @property
    def converted_count(self) -> int:
        return sum(
            formula.status is ConversionStatus.CONVERTED
            for formula in self.formulas
        )

    @property
    def failed_count(self) -> int:
        return sum(
            formula.status is ConversionStatus.FAILED
            for formula in self.formulas
        )


class FormulaConverter:

    SYMBOL_MAP = {
        "α": r"\alpha",
        "β": r"\beta",
        "γ": r"\gamma",
        "δ": r"\delta",
        "ε": r"\epsilon",
        "θ": r"\theta",
        "λ": r"\lambda",
        "μ": r"\mu",
        "π": r"\pi",
        "ρ": r"\rho",
        "σ": r"\sigma",
        "τ": r"\tau",
        "φ": r"\phi",
        "ω": r"\omega",
        "Γ": r"\Gamma",
        "Δ": r"\Delta",
        "Θ": r"\Theta",
        "Λ": r"\Lambda",
        "Π": r"\Pi",
        "Σ": r"\Sigma",
        "Φ": r"\Phi",
        "Ω": r"\Omega",
        "∞": r"\infty",
        "∑": r"\sum",
        "∏": r"\prod",
        "∫": r"\int",
        "∂": r"\partial",
        "∇": r"\nabla",
        "√": r"\sqrt",
        "×": r"\times",
        "÷": r"\div",
        "±": r"\pm",
        "∓": r"\mp",
        "≤": r"\leq",
        "≥": r"\geq",
        "≠": r"\neq",
        "≈": r"\approx",
        "≡": r"\equiv",
        "∝": r"\propto",
        "∈": r"\in",
        "∉": r"\notin",
        "⊂": r"\subset",
        "⊆": r"\subseteq",
        "∪": r"\cup",
        "∩": r"\cap",
        "∅": r"\emptyset",
        "∀": r"\forall",
        "∃": r"\exists",
        "∧": r"\land",
        "∨": r"\lor",
        "¬": r"\neg",
        "→": r"\rightarrow",
        "←": r"\leftarrow",
        "↔": r"\leftrightarrow",
        "⇒": r"\Rightarrow",
        "⇔": r"\Leftrightarrow",
        "∠": r"\angle",
        "°": r"^\circ",
        "′": r"'",
        "″": r"''",
        "·": r"\cdot",
        "…": r"\ldots",
    }

    SUPERSCRIPT_MAP = {
        "⁰": "0",
        "¹": "1",
        "²": "2",
        "³": "3",
        "⁴": "4",
        "⁵": "5",
        "⁶": "6",
        "⁷": "7",
        "⁸": "8",
        "⁹": "9",
        "⁺": "+",
        "⁻": "-",
        "⁼": "=",
        "⁽": "(",
        "⁾": ")",
        "ⁿ": "n",
        "ⁱ": "i",
    }

    SUBSCRIPT_MAP = {
        "₀": "0",
        "₁": "1",
        "₂": "2",
        "₃": "3",
        "₄": "4",
        "₅": "5",
        "₆": "6",
        "₇": "7",
        "₈": "8",
        "₉": "9",
        "₊": "+",
        "₋": "-",
        "₌": "=",
        "₍": "(",
        "₎": ")",
        "ₐ": "a",
        "ₑ": "e",
        "ₕ": "h",
        "ᵢ": "i",
        "ⱼ": "j",
        "ₖ": "k",
        "ₗ": "l",
        "ₘ": "m",
        "ₙ": "n",
        "ₒ": "o",
        "ₚ": "p",
        "ᵣ": "r",
        "ₛ": "s",
        "ₜ": "t",
        "ᵤ": "u",
        "ᵥ": "v",
        "ₓ": "x",
    }

    DELIMITED_FORMULA_PATTERN = re.compile(
        r"(?P<display>\$\$.*?\$\$|\\\[.*?\\\])"
        r"|(?P<inline>\$[^$\n]+\$|\\\(.*?\\\))",
        re.DOTALL,
    )

    LATEX_COMMAND_PATTERN = re.compile(r"\\[a-zA-Z]+|\\[{}$%&#_]")

    def convert(self, text: str) -> FormulaConversionResult:
        """
        Converte fórmulas delimitadas e expressões matemáticas identificáveis.

        Texto comum é preservado. Fórmulas já delimitadas em LaTeX são
        mantidas, evitando conversões duplicadas.
        """
        if not isinstance(text, str):
            raise FormulaConversionError("O conteúdo recebido deve ser textual.")

        formulas: list[FormulaExpression] = []
        converted_parts: list[str] = []
        last_position = 0

        for match in self.DELIMITED_FORMULA_PATTERN.finditer(text):
            converted_parts.append(text[last_position:match.start()])

            original = match.group(0)
            formula_format = (
                FormulaFormat.DISPLAY
                if match.group("display")
                else FormulaFormat.INLINE
            )

            expression = self._remove_delimiters(original)
            formula = self.convert_expression(expression, formula_format)

            formulas.append(formula)
            converted_parts.append(self._restore_delimiters(formula, original))

            last_position = match.end()

        converted_parts.append(text[last_position:])

        return FormulaConversionResult(
            original_text=text,
            converted_text="".join(converted_parts),
            formulas=tuple(formulas),
        )

    def convert_expression(
        self,
        expression: str,
        formula_format: FormulaFormat = FormulaFormat.UNKNOWN,
    ) -> FormulaExpression:
        """Converte uma expressão matemática isolada para LaTeX."""
        if not isinstance(expression, str) or not expression.strip():
            raise FormulaConversionError(
                "A expressão matemática deve ser uma string não vazia."
            )

        original = expression.strip()

        if self._is_latex(original):
            return FormulaExpression(
                original=original,
                latex=original,
                status=ConversionStatus.ALREADY_LATEX,
                format=formula_format,
                confidence=1.0,
            )

        try:
            latex = self._convert_unicode_expression(original)

            if latex == original:
                return FormulaExpression(
                    original=original,
                    latex=original,
                    status=ConversionStatus.UNCHANGED,
                    format=formula_format,
                    confidence=0.5,
                )

            return FormulaExpression(
                original=original,
                latex=latex,
                status=ConversionStatus.CONVERTED,
                format=formula_format,
                confidence=0.95,
            )

        except (ValueError, TypeError, re.error) as error:
            return FormulaExpression(
                original=original,
                latex=original,
                status=ConversionStatus.FAILED,
                format=formula_format,
                confidence=0.0,
            )

    def convert_many(
        self,
        expressions: Iterable[str],
    ) -> tuple[FormulaExpression, ...]:
        """Converte uma coleção de expressões matemáticas."""
        if expressions is None:
            raise FormulaConversionError(
                "A coleção de expressões não foi informada."
            )

        return tuple(
            self.convert_expression(expression)
            for expression in expressions
        )

    def _convert_unicode_expression(self, expression: str) -> str:
        converted = expression

        converted = self._convert_superscripts(converted)
        converted = self._convert_subscripts(converted)
        converted = self._convert_square_roots(converted)

        for symbol, latex_command in sorted(
            self.SYMBOL_MAP.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            converted = converted.replace(symbol, latex_command)

        converted = self._normalize_multiplication(converted)
        converted = self._normalize_whitespace(converted)

        return converted

    def _convert_superscripts(self, text: str) -> str:
        pattern = re.compile(
            r"(?P<base>[A-Za-z0-9)}\]])"
            r"(?P<exponent>[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ]+)"
        )

        def replace(match: re.Match[str]) -> str:
            exponent = "".join(
                self.SUPERSCRIPT_MAP[character]
                for character in match.group("exponent")
            )
            return f"{match.group('base')}^{{{exponent}}}"

        return pattern.sub(replace, text)

    def _convert_subscripts(self, text: str) -> str:
        pattern = re.compile(
            r"(?P<base>[A-Za-z0-9)}\]])"
            r"(?P<index>[₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ]+)"
        )

        def replace(match: re.Match[str]) -> str:
            index = "".join(
                self.SUBSCRIPT_MAP[character]
                for character in match.group("index")
            )
            return f"{match.group('base')}_{{{index}}}"

        return pattern.sub(replace, text)

    @staticmethod
    def _convert_square_roots(text: str) -> str:
        # O símbolo de raiz sem radicando delimitado permanece como comando.
        return text

    @staticmethod
    def _normalize_multiplication(text: str) -> str:
        return re.sub(r"(?<!\\)\*", r"\\cdot ", text)

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        return re.sub(r"[ \t]+", " ", text).strip()

    @classmethod
    def _is_latex(cls, expression: str) -> bool:
        return bool(cls.LATEX_COMMAND_PATTERN.search(expression))

    @staticmethod
    def _remove_delimiters(expression: str) -> str:
        if expression.startswith("$$") and expression.endswith("$$"):
            return expression[2:-2].strip()

        if expression.startswith(r"\[") and expression.endswith(r"\]"):
            return expression[2:-2].strip()

        if expression.startswith("$") and expression.endswith("$"):
            return expression[1:-1].strip()

        if expression.startswith(r"\(") and expression.endswith(r"\)"):
            return expression[2:-2].strip()

        return expression.strip()

    @staticmethod
    def _restore_delimiters(
        formula: FormulaExpression,
        original: str,
    ) -> str:
        if original.startswith("$$") and original.endswith("$$"):
            return f"$${formula.latex}$$"

        if original.startswith(r"\[") and original.endswith(r"\]"):
            return rf"\[{formula.latex}\]"

        if original.startswith("$") and original.endswith("$"):
            return f"${formula.latex}$"

        if original.startswith(r"\(") and original.endswith(r"\)"):
            return rf"\({formula.latex}\)"

        return formula.latex
