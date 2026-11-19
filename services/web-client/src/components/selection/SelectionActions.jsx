import React from "react";

function SelectionActions({
  totalQuestions = 0,
  isLoading = false,
  isProcessing = false,
  onClear,
  onGenerateSimulado,
}) {
  const hasQuestions = totalQuestions > 0;
  const isDisabled = isLoading || isProcessing;

  const handleClear = () => {
    if (!hasQuestions || isDisabled) {
      return;
    }

    onClear?.();
  };

  const handleGenerateSimulado = () => {
    if (!hasQuestions || isDisabled) {
      return;
    }

    onGenerateSimulado?.();
  };

  return (
    <section
      className="selection-actions"
      aria-label="Ações da seleção"
    >
      <div className="selection-actions__information">
        <span className="selection-actions__count">
          {totalQuestions}{" "}
          {totalQuestions === 1 ? "questão selecionada" : "questões selecionadas"}
        </span>
      </div>

      <div className="selection-actions__buttons">
        <button
          type="button"
          className="selection-actions__clear-button"
          onClick={handleClear}
          disabled={!hasQuestions || isDisabled || !onClear}
        >
          Limpar seleção
        </button>

        <button
          type="button"
          className="selection-actions__generate-button"
          onClick={handleGenerateSimulado}
          disabled={
            !hasQuestions ||
            isDisabled ||
            !onGenerateSimulado
          }
        >
          {isProcessing ? "Preparando simulado..." : "Gerar simulado"}
        </button>
      </div>
    </section>
  );
}

export default SelectionActions;
