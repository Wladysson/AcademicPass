import React from "react";

function SelectionList({
  questions = [],
  isLoading = false,
  error = null,
  onViewQuestion,
  onRemoveQuestion,
}) {
  if (isLoading) {
    return (
      <div className="selection-list__loading" role="status">
        Carregando questões selecionadas...
      </div>
    );
  }

  if (error) {
    return (
      <div className="selection-list__error" role="alert">
        {typeof error === "string"
          ? error
          : "Não foi possível carregar as questões selecionadas."}
      </div>
    );
  }

  if (questions.length === 0) {
    return (
      <div className="selection-list__empty">
        <h3>Nenhuma questão selecionada</h3>
        <p>
          Explore o banco de questões e adicione aquelas que deseja utilizar
          posteriormente.
        </p>
      </div>
    );
  }

  const getQuestionTitle = (question) => {
    return (
      question.title ||
      question.statement ||
      question.questionText ||
      `Questão ${question.id}`
    );
  };

  const getQuestionMetadata = (question) => {
    return [
      question.year,
      question.area,
      question.discipline,
      question.institution,
    ].filter(Boolean);
  };

  return (
    <section className="selection-list" aria-label="Questões selecionadas">
      <header className="selection-list__header">
        <h2>Questões selecionadas</h2>
        <span className="selection-list__count">
          {questions.length}{" "}
          {questions.length === 1 ? "questão" : "questões"}
        </span>
      </header>

      <ul className="selection-list__items">
        {questions.map((question) => {
          const questionId = question.id;
          const metadata = getQuestionMetadata(question);

          return (
            <li
              key={questionId}
              className="selection-list__item"
            >
              <article className="selection-list__card">
                <div className="selection-list__content">
                  <h3 className="selection-list__title">
                    {getQuestionTitle(question)}
                  </h3>

                  {metadata.length > 0 && (
                    <ul className="selection-list__metadata">
                      {metadata.map((item, index) => (
                        <li key={`${questionId}-metadata-${index}`}>
                          {item}
                        </li>
                      ))}
                    </ul>
                  )}

                  {question.exam && (
                    <p className="selection-list__exam">
                      Prova: {question.exam}
                    </p>
                  )}
                </div>

                <div className="selection-list__actions">
                  <button
                    type="button"
                    className="selection-list__view-button"
                    onClick={() => onViewQuestion?.(question)}
                    disabled={!onViewQuestion}
                  >
                    Visualizar
                  </button>

                  <button
                    type="button"
                    className="selection-list__remove-button"
                    onClick={() => onRemoveQuestion?.(questionId)}
                    disabled={!onRemoveQuestion}
                    aria-label={`Remover questão ${questionId} da seleção`}
                  >
                    Remover
                  </button>
                </div>
              </article>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default SelectionList;
