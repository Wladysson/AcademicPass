import React, { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function QuestionsByInstitutionChart({
  data = [],
  isLoading = false,
  error = null,
}) {
  const chartData = useMemo(() => {
    return data
      .map((item) => ({
        institution: String(
          item.institution ?? item.name ?? ""
        ).trim(),
        total: Number(item.total ?? item.count ?? 0),
      }))
      .filter(
        (item) =>
          item.institution !== "" &&
          Number.isFinite(item.total) &&
          item.total >= 0
      )
      .sort((first, second) => second.total - first.total);
  }, [data]);

  if (isLoading) {
    return (
      <section
        className="questions-by-institution-chart"
        aria-live="polite"
      >
        Carregando distribuição por instituição...
      </section>
    );
  }

  if (error) {
    return (
      <section
        className="questions-by-institution-chart questions-by-institution-chart--error"
        role="alert"
      >
        {typeof error === "string"
          ? error
          : "Não foi possível carregar a distribuição das questões por instituição."}
      </section>
    );
  }

  if (chartData.length === 0) {
    return (
      <section className="questions-by-institution-chart">
        <header className="questions-by-institution-chart__header">
          <h3>Questões por instituição</h3>
        </header>

        <p className="questions-by-institution-chart__empty">
          Não existem dados disponíveis para esta visualização.
        </p>
      </section>
    );
  }

  return (
    <section
      className="questions-by-institution-chart"
      aria-label="Distribuição de questões por instituição"
    >
      <header className="questions-by-institution-chart__header">
        <h3>Questões por instituição</h3>
        <p>
          Comparação da quantidade de questões associadas a cada instituição.
        </p>
      </header>

      <div
        className="questions-by-institution-chart__container"
        style={{
          height: Math.max(320, chartData.length * 48),
        }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{
              top: 12,
              right: 24,
              left: 24,
              bottom: 12,
            }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              horizontal={false}
            />

            <XAxis
              type="number"
              allowDecimals={false}
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />

            <YAxis
              type="category"
              dataKey="institution"
              width={180}
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />

            <Tooltip
              formatter={(value) => [
                `${Number(value).toLocaleString("pt-BR")} questões`,
                "Quantidade",
              ]}
            />

            <Bar
              dataKey="total"
              name="Questões"
              fill="#2563eb"
              radius={[0, 4, 4, 0]}
              maxBarSize={28}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export default QuestionsByInstitutionChart;
