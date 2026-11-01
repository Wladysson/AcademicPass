
import { useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
import { useSearchStore } from "../stores/searchStore";
import { useSelectionStore } from "../stores/selectionStore";

export default function ProfessorDashboardView() {
  const navigate = useNavigate();

  const {
    user,
    profile,
    logout,
  } = useAuthStore();

  const {
    totalResults,
    questions,
    isLoading: isSearchLoading,
    searchQuestions,
  } = useSearchStore();

  const {
    selections,
    totalSelected,
    isLoading: isSelectionLoading,
    fetchSelections,
  } = useSelectionStore();

  useEffect(() => {
    searchQuestions();
    fetchSelections();
  }, [searchQuestions, fetchSelections]);

  const professorName = useMemo(() => {
    return (
      user?.name ??
      user?.nome ??
      user?.username ??
      "Professor"
    );
  }, [user]);

  const selectedCount = totalSelected ?? selections.length;

  const availableCount = totalResults ?? questions.length;

  async function handleLogout() {
    try {
      await logout();
    } finally {
      navigate("/login", { replace: true });
    }
  }

  return (
    <main className="professor-dashboard">
      <header className="professor-dashboard__header">
        <div>
          <span className="professor-dashboard__eyebrow">
            AcademicPass
          </span>

          <h1>Painel do professor</h1>

          <p>
            Bem-vindo, {professorName}. Gerencie questões e prepare
            simulados para seus alunos.
          </p>
        </div>

        <div className="professor-dashboard__header-actions">
          <span className="professor-dashboard__profile">
            {profile ?? "PROFESSOR"}
          </span>

          <button
            type="button"
            onClick={handleLogout}
            className="professor-dashboard__logout"
          >
            Sair
          </button>
        </div>
      </header>

      <section
        className="professor-dashboard__indicators"
        aria-label="Indicadores da plataforma"
      >
        <article className="professor-dashboard__indicator">
          <span>Questões encontradas</span>

          <strong>
            {isSearchLoading ? "..." : availableCount}
          </strong>

          <p>Questões disponíveis na busca atual.</p>
        </article>

        <article className="professor-dashboard__indicator">
          <span>Questões selecionadas</span>

          <strong>
            {isSelectionLoading ? "..." : selectedCount}
          </strong>

          <p>Questões reunidas na sua seleção.</p>
        </article>

        <article className="professor-dashboard__indicator">
          <span>Perfil de acesso</span>

          <strong>Professor</strong>

          <p>Acesso ao ambiente de gerenciamento acadêmico.</p>
        </article>
      </section>

      <section className="professor-dashboard__workspace">
        <div className="professor-dashboard__section-heading">
          <h2>Área de trabalho</h2>

          <p>
            Acesse os recursos disponíveis para preparar suas atividades.
          </p>
        </div>

        <div className="professor-dashboard__cards">
          <article className="professor-dashboard__card">
            <div>
              <h3>Banco de questões</h3>

              <p>
                Pesquise questões do ENADE utilizando filtros por ano,
                área, disciplina, prova e instituição.
              </p>
            </div>

            <button
              type="button"
              onClick={() => navigate("/search")}
            >
              Acessar busca
            </button>
          </article>

          <article className="professor-dashboard__card">
            <div>
              <h3>Minha seleção</h3>

              <p>
                Consulte e organize as questões escolhidas para a
                elaboração de atividades.
              </p>
            </div>

            <button
              type="button"
              onClick={() => navigate("/selection")}
            >
              Gerenciar seleção
            </button>
          </article>

          <article className="professor-dashboard__card">
            <div>
              <h3>Simulados</h3>

              <p>
                Acesse o espaço destinado à criação e ao gerenciamento
                de simulados.
              </p>
            </div>

            <button
              type="button"
              onClick={() => navigate("/simulados")}
            >
              Acessar simulados
            </button>
          </article>
        </div>
      </section>

      <section className="professor-dashboard__recent">
        <div className="professor-dashboard__section-heading">
          <h2>Questões selecionadas recentemente</h2>

          <button
            type="button"
            onClick={() => navigate("/selection")}
          >
            Ver seleção completa
          </button>
        </div>

        {isSelectionLoading ? (
          <p role="status">Carregando seleção...</p>
        ) : selections.length === 0 ? (
          <div className="professor-dashboard__empty">
            <p>
              Você ainda não adicionou questões à sua seleção.
            </p>

            <button
              type="button"
              onClick={() => navigate("/search")}
            >
              Buscar questões
            </button>
          </div>
        ) : (
          <div className="professor-dashboard__recent-list">
            {selections.slice(0, 5).map((selection, index) => {
              const question = selection.question ?? selection;

              const questionId =
                selection.questionId ??
                selection.question_id ??
                question.id ??
                question.questionId;

              const questionNumber =
                question.number ??
                question.question_number ??
                "Não informado";

              const statement =
                question.statement ??
                question.question_text ??
                question.enunciado ??
                question.text ??
                "Enunciado não disponível.";

              return (
                <article
                  key={selection.id ?? questionId ?? index}
                  className="professor-dashboard__recent-item"
                >
                  <div>
                    <strong>Questão {questionNumber}</strong>

                    <p>{statement}</p>
                  </div>

                  <button
                    type="button"
                    disabled={questionId == null}
                    onClick={() => navigate(`/questions/${questionId}`)}
                  >
                    Visualizar
                  </button>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}