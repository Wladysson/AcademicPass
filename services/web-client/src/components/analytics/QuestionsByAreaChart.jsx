import React, { useMemo } from "react";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

function QuestionsByAreaChart({
  data = [],
  isLoading = false,
  error = null,
}) {
  const chartData = useMemo(() => {
    return data
      .map((item) => ({
        area: String(item.area ?? item.name ?? "").trim(),
        total: Number(item.total ?? item.count ?? 0),
      }))
      .filter(
        (item) =>
          item.area !== "" &&
          Number.isFinite(item.total) &&
          item.total >= 0
      );
  }, [data]);

  const totalQuestions = useMemo(() => {
    return chartData.reduce(
      (total, item) => total + item.total,
      0
    );
  }, [chartData]);

  if (isLoading) {
    return (
      <section
        className="questions-by-area-chart"
        aria-live="polite"
      >
        Carregando distribuição por área...
      </section>
    );
  }

  if (error) {
    return (
      <section
        className="questions-by-area-chart questions-by-area-chart--error"
        role="alert"
      >
        {typeof error === "string"
          ? error
          : "Não foi possível carregar a distribuição das questões por área."}
      </section>
    );
  }

  if (chartData.length === 0 || totalQuestions === 0) {
    return (
      <section className="questions-by-area-chart">
        <header className="questions-by-area-chart__header">
          <h3>Questões por área</h3>
        </header>

        <p className="questions-by-area-chart__empty">
          Não existem dados disponíveis para esta visualização.
        </p>
      </section>
    );
  }

  return (
    <section
      className="questions-by-area-chart"
      aria-label="Distribuição de questões por área de conhecimento"
    >
      <header className="questions-by-area-chart__header">
        <h3>Questões por área</h3>
        <p>
          Distribuição das questões entre as áreas de conhecimento.
        </p>
      </header>

      <div className="questions-by-area-chart__container">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              dataKey="total"
              nameKey="area"
              cx="50%"
              cy="50%"
              outerRadius="75%"
              innerRadius="45%"
              paddingAngle={2}
              label={({ name, percent }) =>
                `${name} (${(percent * 100).toFixed(1)}%)`
              }
              labelLine
            >
              {chartData.map((item) => (
                <Cell
                  key={item.area}
                  fill={undefined}
                />
              ))}
            </Pie>

            <Tooltip
              formatter={(value, name) => [
                `${Number(value).toLocaleString("pt-BR")} questões`,
                name,
              ]}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <div className="questions-by-area-chart__total">
        <span>Total de questões</span>
        <strong>
          {totalQuestions.toLocaleString("pt-BR")}
        </strong>
      </div>
    </section>
  );
}

export default QuestionsByAreaChart;
