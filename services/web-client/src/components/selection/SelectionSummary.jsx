import React, { useMemo } from "react";

function SelectionSummary({
  questions = [],
  isLoading = false,
}) {
  const summary = useMemo(() => {
    const countBy = (property) => {
      return questions.reduce((result, question) => {
        const value = question[property];

        if (value !== undefined && value !== null && value !== "") {
          result[value] = (result[value] || 0) + 1;
        }

        return result;
      }, {});
    };

    return {
      total: questions.length,
      byYear: countBy("year"),
      byArea: countBy("area"),
      byDiscipline: countBy("discipline"),
    };
  }, [questions]);

  const renderDistribution = (title, distribution) => {
    const entries = Object.entries(distribution).sort(
      ([first], [second]) => first.localeCompare(second, "pt-BR", {
        numeric: true,
      })
    );

    if (entries.length === 0) {
      return (
        <div className="selection-summary__empty">
          Nenhuma informação disponível.
        </div>
      );
    }

    return (
      <section className="selection-summary__distribution">
        <h4>{title}</h4>

        <ul>
          {entries.map(([label, count]) => (
            <li key={label}>
              <span>{label}</span>
              <strong>{count}</strong>
            </li>
          ))}
        </ul>
      </section>
    );
  };

  if (isLoading) {
    return (
      <section
        className="selection-summary selection-summary--loading"
        aria-live="polite"
      >
        Carregando resumo da seleção...
      </section>
    );
  }

  return (
    <section
      className="selection-summary"
      aria-label="Resumo das questões selecionadas"
    >
      <header className="selection-summary__header">
        <h2>Resumo da seleção</h2>
      </header>

      <div className="selection-summary__total">
        <span>Total de questões</span>
        <strong>{summary.total}</strong>
      </div>

      <div className="selection-summary__distributions">
        {renderDistribution("Distribuição por ano", summary.byYear)}
        {renderDistribution("Distribuição por área", summary.byArea)}
        {renderDistribution(
          "Distribuição por disciplina",
          summary.byDiscipline
        )}
      </div>
    </section>
  );
}

export default SelectionSummary;
