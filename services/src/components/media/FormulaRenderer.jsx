import { useMemo } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

function normalizeFormula(value) {
  let normalized = String(value ?? "").trim();

  if (
    normalized.startsWith("$$") &&
    normalized.endsWith("$$")
  ) {
    normalized = normalized.slice(2, -2).trim();
  } else if (
    normalized.startsWith("\\[") &&
    normalized.endsWith("\\]")
  ) {
    normalized = normalized.slice(2, -2).trim();
  } else if (
    normalized.startsWith("\\(") &&
    normalized.endsWith("\\)")
  ) {
    normalized = normalized.slice(2, -2).trim();
  } else if (
    normalized.startsWith("$") &&
    normalized.endsWith("$")
  ) {
    normalized = normalized.slice(1, -1).trim();
  }

  return normalized;
}

export default function FormulaRenderer({
  formula,
  displayMode = false,
  className = "",
  errorMessage = "Não foi possível renderizar esta fórmula.",
}) {
  const latex = useMemo(() => {
    if (typeof formula === "string") {
      return normalizeFormula(formula);
    }

    if (formula && typeof formula === "object") {
      return normalizeFormula(
        formula.latex ?? formula.content ?? formula.expression ?? ""
      );
    }

    return "";
  }, [formula]);

  const renderedFormula = useMemo(() => {
    if (!latex) {
      return null;
    }

    try {
      return katex.renderToString(latex, {
        displayMode,
        throwOnError: false,
        strict: "warn",
        trust: false,
        output: "htmlAndMathml",
      });
    } catch {
      return null;
    }
  }, [latex, displayMode]);

  if (!latex) {
    return null;
  }

  if (!renderedFormula) {
    return (
      <span
        className={`formula-renderer formula-renderer--error ${className}`}
        role="status"
      >
        {errorMessage}
      </span>
    );
  }

  const Container = displayMode ? "div" : "span";

  return (
    <Container
      className={`formula-renderer ${
        displayMode
          ? "formula-renderer--block"
          : "formula-renderer--inline"
      } ${className}`.trim()}
      role="math"
      aria-label={`Expressão matemática: ${latex}`}
      dangerouslySetInnerHTML={{
        __html: renderedFormula,
      }}
    />
  );
}
