import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import searchApi from "../api/searchApi";
import useSelectionStore from "../stores/selectionStore";

function QuestionDetailView() {
  const { questionId } = useParams();
  const navigate = useNavigate();

  const addQuestion = useSelectionStore((state) => state.addQuestion);
  const isQuestionSelected = useSelectionStore(
    (state) => state.isQuestionSelected
  );

  const [question, setQuestion] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAdding, setIsAdding] = useState(false);
  const [error, setError] = useState(null);

  const [selectedAlternative, setSelectedAlternative] = useState(null);

  const alternatives = question?.alternatives || [];
  const questionIsSelected = isQuestionSelected(questionId);

  useEffect(() => {
    let active = true;

    async function loadQuestion() {
      setIsLoading(true);
      setError(null);

      try {
        const response = await searchApi.getQuestionById(questionId);

        if (active) {
          setQuestion(response?.question || response?.data || response);
        }
      } catch (err) {
        if (active) {
          setError(
            err.message || "Não foi possível carregar os detalhes da questão."
          );
        }
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }

    if (questionId) {
      loadQuestion();
    } else {
      setError("Identificador da questão não informado.");
      setIsLoading(false);
    }

    return () => {
      active = false;
    };
  }, [questionId]);

  async function handleAddQuestion() {
    setIsAdding(true);
    setError(null);

    try {
      await addQuestion(questionId);
    } catch (err) {
      setError(err.message || "Não foi possível adicionar a questão.");
    } finally {
      setIsAdding(false);
    }
  }

  function renderMediaContent(items, renderItem) {
    if (!Array.isArray(items) || items.length === 0) {
      return null;
    }

    return items.map((item, index) => renderItem(item, index));
  }

  if (isLoading) {
    return (
      <main className="question-detail-page">
        <p>Carregando questão...</p>
      </main>
    );
  }

  if (error && !question) {
    return (
      <main className="question-detail-page">
        <div className="detail-error" role="alert">
          {error}
        </div>

        <button type="button" onClick={() => navigate(-1)}>
          Voltar
        </button>
      </main>
    );
  }

  if (!question) {
    return (
      <main className="question-detail-page">
        <p>Questão não encontrada.</p>

        <button type="button" onClick={() => navigate(-1)}>
          Voltar
        </button>
      </main>
    );
  }

  const metadata = question.metadata || {};

  const statement =
    question.statement ||
    question.question_text ||
    question.statement_text ||
    "";

  return (
    <main className="question-detail-page">
      <header className="detail-header">
        <button type="button" onClick={() => navigate(-1)}>
          Voltar
        </button>

        <h1>Detalhes da questão</h1>

        <button
          type="button"
          onClick={handleAddQuestion}
          disabled={questionIsSelected || isAdding}
        >
          {questionIsSelected
            ? "Adicionada à seleção"
            : isAdding
              ? "Adicionando..."
              : "Adicionar à seleção"}
        </button>
      </header>

      {error && (
        <div className="detail-error" role="alert">
          {error}
        </div>
      )}

      <article className="question-detail-card">
        <section className="question-heading">
          <h2>
            Questão {question.number || question.question_number || ""}
          </h2>

          <div className="question-metadata">
            <span>
              Ano: {metadata.year || question.year || "Não informado"}
            </span>

            <span>
              Área: {metadata.area || question.area || "Não informada"}
            </span>

            <span>
              Disciplina:{" "}
              {metadata.discipline ||
                question.discipline ||
                "Não informada"}
            </span>

            <span>
              Instituição:{" "}
              {metadata.institution ||
                question.institution ||
                "Não informada"}
            </span>
          </div>
        </section>

        <section className="question-statement">
          <h3>Enunciado</h3>

          <p>{statement || "Enunciado não disponível."}</p>
        </section>

        {alternatives.length > 0 && (
          <section className="question-alternatives">
            <h3>Alternativas</h3>

            <div className="alternative-list">
              {alternatives.map((alternative, index) => {
                const alternativeId =
                  alternative.id ||
                  alternative.letter ||
                  alternative.label ||
                  String(index);

                const alternativeLabel =
                  alternative.letter ||
                  alternative.label ||
                  String.fromCharCode(65 + index);

                const alternativeText =
                  alternative.text ||
                  alternative.content ||
                  alternative.description ||
                  "";

                return (
                  <button
                    type="button"
                    key={alternativeId}
                    className={`alternative-item ${
                      selectedAlternative === alternativeId
                        ? "selected"
                        : ""
                    }`}
                    onClick={() => setSelectedAlternative(alternativeId)}
                  >
                    <strong>{alternativeLabel}.</strong>
                    <span>{alternativeText}</span>
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {renderMediaContent(question.formulas, (formula, index) => (
          <section className="question-media" key={`formula-${index}`}>
            <h3>Fórmula</h3>
            <pre>{formula.latex || formula.content || formula}</pre>
          </section>
        ))}

        {renderMediaContent(question.tables, (table, index) => (
          <section className="question-media" key={`table-${index}`}>
            <h3>Tabela {index + 1}</h3>
            <pre>{table.markdown || table.content || table}</pre>
          </section>
        ))}

        {renderMediaContent(question.diagrams, (diagram, index) => (
          <section className="question-media" key={`diagram-${index}`}>
            <h3>Diagrama {index + 1}</h3>
            <pre>{diagram.mermaid || diagram.content || diagram}</pre>
          </section>
        ))}

        {question.competencies?.length > 0 && (
          <section className="question-competencies">
            <h3>Competências relacionadas</h3>

            <ul>
              {question.competencies.map((competency, index) => (
                <li key={competency.id || index}>
                  {competency.name || competency.description || competency}
                </li>
              ))}
            </ul>
          </section>
        )}

        {question.correct_answer && (
          <section className="question-answer">
            <h3>Gabarito</h3>
            <p>{question.correct_answer}</p>
          </section>
        )}
      </article>
    </main>
  );
}

export default QuestionDetailView;