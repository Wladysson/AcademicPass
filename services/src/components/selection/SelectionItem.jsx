import React from "react";

function SelectionItem({
  question,
  onView,
  onRemove,
}) {
  if (!question) {
    return null;
  }

  const questionId = question.id;

  const title =
    question.title ||
    question.statement ||
    question.questionText ||
    `Questão ${questionId}`;

  const metadata = [
    question.year,
    question.area,
    question.discipline,
    question.institution,
  ].filter(Boolean);

  return (
    <article className="selection-item">
      <div className="selection-item__content">
        <h3 className="selection-item__title">
          {title}
        </h3>

        {metadata.length > 0 && (
          <ul className="selection-item__metadata">
            {metadata.map((value, index) => (
              <li key={`${questionId}-metadata-${index}`}>
                {value}
              </li>
            ))}
          </ul>
        )}

        {question.exam && (
          <p className="selection-item__exam">
            Prova: {question.exam}
          </p>
        )}

        {question.code && (
          <p className="selection-item__code">
            Código: {question.code}
          </p>
        )}
      </div>

      <div className="selection-item__actions">
        <button
          type="button"
          className="selection-item__view-button"
          onClick={() => onView?.(question)}
          disabled={!onView}
        >
          Visualizar
        </button>

        <button
          type="button"
          className="selection-item__remove-button"
          onClick={() => onRemove?.(questionId)}
          disabled={!onRemove}
          aria-label={`Remover questão ${questionId} da seleção`}
        >
          Remover
        </button>
      </div>
    </article>
  );
}

export default SelectionItem;
