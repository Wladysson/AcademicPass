import React from "react";

function AnalyticsOverview({
  analytics = {},
  isLoading = false,
  error = null,
}) {
  const {
    totalQuestions = 0,
    totalYears = 0,
    totalAreas = 0,
    totalDisciplines = 0,
    totalExams = 0,
    totalInstitutions = 0,
  } = analytics;

  const indicators = [
    {
      label: "Questões indexadas",
      value: totalQuestions,
    },
    {
      label: "Anos disponíveis",
      value: totalYears,
    },
    {
      label: "Áreas de conhecimento",
      value: totalAreas,
    },
    {
      label: "Disciplinas",
      value: totalDisciplines,
    },
    {
      label: "Provas",
      value: totalExams,
    },
    {
      label: "Instituições",
      value: totalInstitutions,
    },
  ];

  if (isLoading) {
    return (
      <section
        className="analytics-overview analytics-overview--loading"
        aria-live="polite"
      >
        Carregando indicadores acadêmicos...
      </section>
    );
  }

  if (error) {
    return (
      <section
        className="analytics-overview analytics-overview--error"
        role="alert"
      >
        {typeof error === "string"
          ? error
          : "Não foi possível carregar os indicadores acadêmicos."}
      </section>
    );
  }

  return (
    <section
      className="analytics-overview"
      aria-label="Visão geral das estatísticas acadêmicas"
    >
      <header className="analytics-overview__header">
        <h2>Visão geral</h2>
        <p>
          Indicadores consolidados do banco de questões acadêmicas.
        </p>
      </header>

      <div className="analytics-overview__grid">
        {indicators.map((indicator) => (
          <article
            key={indicator.label}
            className="analytics-overview__card"
          >
            <span className="analytics-overview__label">
              {indicator.label}
            </span>

            <strong className="analytics-overview__value">
              {Number(indicator.value).toLocaleString("pt-BR")}
            </strong>
          </article>
        ))}
      </div>
    </section>
  );
}

export default AnalyticsOverview;
