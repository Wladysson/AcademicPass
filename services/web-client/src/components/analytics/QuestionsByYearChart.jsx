import React, { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function QuestionsByYearChart({
  data = [],
  isLoading = false,
  error = null,
}) {
  const chartData = useMemo(() => {
    return data
      .map((item) => ({
        year: String(item.year),
        total: Number(item.total ?? item.count ?? 0),
      }))
      .filter(
        (item) =>
          item.year.trim() !== "" &&
          Number.isFinite(item.total)
      )
      .sort(
        (first, second) =>
          Number(first.year) - Number(second.year)
      );
  }, [data]);

  if (isLoading) {
    return (
      <section
        className="questions-by-year-chart"
        aria-live="polite"
      >
        Carregando distribuição por ano...
      </section>
    );
  }

  if (error) {
    return (
      <section
        className="questions-by-year-chart questions-by-year-chart--error"
        role="alert"
      >
        {typeof error === "string"
          ? error
          : "Não foi possível carregar a distribuição das questões por ano."}
      </section>
    );
  }

  if (chartData.length === 0) {
    return (
      <section className="questions-by-year-chart">
        <header className="questions-by-year-chart__header">
          <h3>Questões por ano</h3>
        </header>

        <p className="questions-by-year-chart__empty">
          Não existem dados disponíveis para esta visualização.
        </p>
      </section>
    );
  }

  return (
    <section
      className="questions-by-year-chart"
      aria-label="Distribuição de questões por ano"
    >
      <header className="questions-by-year-chart__header">
        <h3>Questões por ano</h3>
        <p>
          Evolução da quantidade de questões por ano de publicação.
        </p>
      </header>

      <div className="questions-by-year-chart__container">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={{
              top: 16,
              right: 20,
              left: 8,
              bottom: 8,
            }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
            />

            <XAxis
              dataKey="year"
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />

            <YAxis
              allowDecimals={false}
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />

            <Tooltip
              formatter={(value) => [
                Number(value).toLocaleString("pt-BR"),
                "Questões",
              ]}
              labelFormatter={(label) => `Ano: ${label}`}
            />

            <Line
              type="monotone"
              dataKey="total"
              name="Questões"
              stroke="#2563eb"
              strokeWidth={2}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export default QuestionsByYearChart;
