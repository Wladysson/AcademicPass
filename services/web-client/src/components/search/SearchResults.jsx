import SearchResultCard from "./SearchResultCard";

export default function SearchResults({
  questions = [],
  isLoading = false,
  error = null,
  totalResults = 0,
  onViewQuestion,
  onToggleSelection,
  isQuestionSelected,
  processingQuestionId = null,
}) {
  if (isLoading) {
    return (
      <section
        className="search-results search-results--loading"
        aria-live="polite"
        aria-busy="true"
      >
        <p>Buscando questões...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section
        className="search-results search-results--error"
        role="alert"
      >
        <h2>Não foi possível carregar os resultados</h2>
        <p>{error}</p>
      </section>
    );
  }

  if (!questions.length) {
    return (
      <section className="search-results search-results--empty">
        <h2>Nenhuma questão encontrada</h2>
        <p>
          Não encontramos questões para os critérios informados.
          Experimente modificar os termos ou filtros da pesquisa.
        </p>
      </section>
    );
  }

  return (
    <section
      className="search-results"
      aria-label="Resultados da pesquisa"
    >
      <header className="search-results__header">
        <h2>Resultados da pesquisa</h2>

        <span className="search-results__count">
          {totalResults}{" "}
          {totalResults === 1
            ? "questão encontrada"
            : "questões encontradas"}
        </span>
      </header>

      <div className="search-results__list">
        {questions.map((question, index) => {
          const questionId =
            question.id ??
            question.question_id ??
            question.questionId;

          const selected = Boolean(
            typeof isQuestionSelected === "function" &&
            isQuestionSelected(questionId)
          );

          return (
            <SearchResultCard
              key={questionId ?? index}
              question={question}
              isSelected={selected}
              isProcessing={processingQuestionId === questionId}
              onView={onViewQuestion}
              onToggleSelection={onToggleSelection}
            />
          );
        })}
      </div>
    </section>
  );
}