import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSelectionStore } from "../stores/selectionStore";

function getQuestionId(selection) {
  return (
    selection.questionId ??
    selection.question_id ??
    selection.question?.questionId ??
    selection.question?.question_id ??
    selection.question?.id
  );
}

function getSelectionId(selection) {
  return selection.id ?? selection.selectionId ?? selection.selection_id;
}

function getQuestionTitle(selection) {
  const question = selection.question ?? selection;

  return (
    question.statement ??
    question.question_text ??
    question.enunciado ??
    question.text ??
    "Enunciado não disponível."
  );
}

function getQuestionNumber(selection) {
  const question = selection.question ?? selection;

  return (
    question.number ??
    question.question_number ??
    question.questionNumber ??
    "Não informado"
  );
}

function getQuestionMetadata(selection) {
  const question = selection.question ?? selection;
  const metadata = question.metadata ?? {};

  return {
    year: question.year ?? metadata.year ?? metadata.ano,
    area: question.area ?? metadata.area,
    discipline: question.discipline ?? metadata.discipline,
    institution: question.institution ?? metadata.institution,
  };
}

export default function SelectionView() {
  const navigate = useNavigate();

  const {
    selections,
    totalSelected,
    isLoading,
    error,
    fetchSelections,
    removeQuestion,
    clearSelections,
    clearError,
  } = useSelectionStore();

  const [removingId, setRemovingId] = useState(null);
  const [isClearing, setIsClearing] = useState(false);
  const [actionError, setActionError] = useState(null);

  useEffect(() => {
    fetchSelections();
  }, [fetchSelections]);

  async function handleRemove(selection) {
    const selectionId = getSelectionId(selection);

    if (selectionId == null) {
      setActionError(
        "Não foi possível identificar o item selecionado para remoção."
      );
      return;
    }

    setRemovingId(selectionId);
    setActionError(null);

    try {
      await removeQuestion(selectionId);
    } catch (err) {
      setActionError(
        err?.message ?? "Não foi possível remover a questão da seleção."
      );
    } finally {
      setRemovingId(null);
    }
  }

  async function handleClear() {
    if (selections.length === 0) {
      return;
    }

    const confirmed = window.confirm(
      "Deseja realmente remover todas as questões da seleção?"
    );

    if (!confirmed) {
      return;
    }

    setIsClearing(true);
    setActionError(null);

    try {
      await clearSelections();
    } catch (err) {
      setActionError(
        err?.message ?? "Não foi possível limpar a seleção."
      );
    } finally {
      setIsClearing(false);
    }
  }

  function handleOpenQuestion(selection) {
    const questionId = getQuestionId(selection);

    if (questionId == null) {
      setActionError(
        "Não foi possível identificar a questão para abrir seus detalhes."
      );
      return;
    }

    navigate(`/questions/${questionId}`);
  }

  function handleSearch() {
    navigate("/search");
  }

  const displayedError = actionError ?? error;

  return (
    <main className="selection-view">
      <header className="selection-view__header">
        <div>
          <h1>Minha seleção</h1>
          <p>
            Organize as questões que deseja utilizar na preparação dos seus
            simulados.
          </p>
        </div>

        <div className="selection-view__actions">
          <button
            type="button"
            onClick={handleSearch}
            className="selection-view__search-button"
          >
            Buscar questões
          </button>

          <button
            type="button"
            onClick={handleClear}
            disabled={isLoading || isClearing || selections.length === 0}
            className="selection-view__clear-button"
          >
            {isClearing ? "Limpando..." : "Limpar seleção"}
          </button>
        </div>
      </header>

      <section className="selection-view__summary">
        <span>Questões selecionadas</span>
        <strong>{totalSelected ?? selections.length}</strong>
      </section>

      {displayedError && (
        <div className="selection-view__error" role="alert">
          <p>{displayedError}</p>

          <button
            type="button"
            onClick={() => {
              setActionError(null);
              clearError?.();
            }}
          >
            Fechar
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="selection-view__loading" role="status">
          Carregando questões selecionadas...
        </div>
      ) : selections.length === 0 ? (
        <section className="selection-view__empty">
          <h2>Nenhuma questão selecionada</h2>
          <p>
            Explore o banco de questões do ENADE e adicione os itens que deseja
            utilizar posteriormente.
          </p>

          <button type="button" onClick={handleSearch}>
            Explorar questões
          </button>
        </section>
      ) : (
        <section className="selection-view__list">
          {selections.map((selection, index) => {
            const selectionId = getSelectionId(selection);
            const metadata = getQuestionMetadata(selection);
            const questionId = getQuestionId(selection);

            return (
              <article
                key={selectionId ?? questionId ?? index}
                className="selection-view__item"
              >
                <div className="selection-view__item-header">
                  <h2>
                    Questão {getQuestionNumber(selection)}
                  </h2>

                  {metadata.year && (
                    <span>{metadata.year}</span>
                  )}
                </div>

                <p className="selection-view__item-statement">
                  {getQuestionTitle(selection)}
                </p>

                <div className="selection-view__metadata">
                  {metadata.area && (
                    <span>Área: {metadata.area}</span>
                  )}

                  {metadata.discipline && (
                    <span>Disciplina: {metadata.discipline}</span>
                  )}

                  {metadata.institution && (
                    <span>Instituição: {metadata.institution}</span>
                  )}
                </div>

                <footer className="selection-view__item-actions">
                  <button
                    type="button"
                    onClick={() => handleOpenQuestion(selection)}
                    disabled={questionId == null}
                  >
                    Visualizar questão
                  </button>

                  <button
                    type="button"
                    onClick={() => handleRemove(selection)}
                    disabled={
                      removingId === selectionId ||
                      selectionId == null
                    }
                  >
                    {removingId === selectionId
                      ? "Removendo..."
                      : "Remover"}
                  </button>
                </footer>
              </article>
            );
          })}
        </section>
      )}
    </main>
  );
}
