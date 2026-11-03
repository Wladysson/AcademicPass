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

function QuestionsByExamChart({
  data = [],
  isLoading = false,
  error = null,
}) {
  const chartData = useMemo(() => {
    return data
      .map((item) => ({
        exam: String(
          item.exam ?? item.name ?? ""
        ).trim(),
        total: Number(item.total ?? item.count ?? 0),
      }))
      .filter(
        (item) =>
          item.exam !== "" &&
          Number.isFinite(item.total) &&
          item.total >= 0
      )
      .sort((first, second) => second.total - first.total);
  }, [data]);

  if (isLoading) {
    return (
      <section
        className="questions-by-exam-chart"
        aria-live="polite"
      >
        Carregando distribuição por prova...
      </section>
    );
  }

  if (error) {
    return (
      <section
        className="questions-by-exam-chart questions-by-exam-chart--error"
        role="alert"
      >
        {typeof error === "string"
          ? error
          : "Não foi possível carregar a distribuição das questões por prova."}
      </section>
    );
  }

  if (chartData.length === 0) {
    return (
      <section className="questions-by-exam-chart">
        <header className="questions-by-exam-chart__header">
          <h3>Questões por prova</h3>
        </header>

        <p className="questions-by-exam-chart__empty">
          Não existem dados disponíveis para esta visualização.
        </p>
      </section>
    );
  }

  return (
    <section
      className="questions-by-exam-chart"
      aria-label="Distribuição de questões por prova"
    >
      <header className="questions-by-exam-chart__header">
        <h3>Questões por prova</h3>
        <p>
          Comparação da quantidade de questões disponíveis em cada prova.
        </p>
      </header>

      <div
        className="questions-by-exam-chart__container"
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
              dataKey="exam"
              width={150}
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

export default QuestionsByExamChart;
