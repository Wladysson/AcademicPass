import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import useSearchStore from "../stores/searchStore";
import useSelectionStore from "../stores/selectionStore";
import useAuthStore from "../stores/authStore";

function SearchView() {
  const navigate = useNavigate();

  const filters = useSearchStore((state) => state.filters);
  const questions = useSearchStore((state) => state.questions);
  const totalResults = useSearchStore((state) => state.totalResults);
  const currentPage = useSearchStore((state) => state.currentPage);
  const pageSize = useSearchStore((state) => state.pageSize);
  const isLoading = useSearchStore((state) => state.isLoading);
  const error = useSearchStore((state) => state.error);

  const setFilter = useSearchStore((state) => state.setFilter);
  const searchQuestions = useSearchStore((state) => state.searchQuestions);
  const resetSearch = useSearchStore((state) => state.resetSearch);
  const nextPage = useSearchStore((state) => state.nextPage);
  const previousPage = useSearchStore((state) => state.previousPage);
  const clearSearchError = useSearchStore((state) => state.clearError);

  const addQuestion = useSelectionStore((state) => state.addQuestion);
  const isQuestionSelected = useSelectionStore(
    (state) => state.isQuestionSelected
  );

  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);

  const [selectedQuestionId, setSelectedQuestionId] = useState(null);
  const [selectionError, setSelectionError] = useState(null);

  const totalPages = Math.ceil(totalResults / pageSize);

  useEffect(() => {
    searchQuestions().catch(() => {});
  }, []);

  function handleFilterChange(event) {
    const { name, value } = event.target;

    setFilter(
      name,
      name === "year" ? (value ? Number(value) : null) : value || null
    );
  }

  async function handleSearch(event) {
    event.preventDefault();
    await searchQuestions();
  }

  function handleReset() {
    resetSearch();
    clearSearchError();
  }

  async function handleAddQuestion(questionId) {
    setSelectedQuestionId(questionId);
    setSelectionError(null);

    try {
      await addQuestion(questionId);
    } catch (error) {
      setSelectionError(error.message);
    } finally {
      setSelectedQuestionId(null);
    }
  }

  async function handleLogout() {
    try {
      await logout();
      navigate("/login", { replace: true });
    } catch {
      navigate("/login", { replace: true });
    }
  }

  return (
    <main className="search-page">
      <header className="page-header">
        <div>
          <h1>AcademicPass</h1>
          <p>Pesquisa de questões do ENADE</p>
        </div>

        <div className="user-session">
          <span>{user?.name || user?.username || "Usuário"}</span>

          <button type="button" onClick={handleLogout}>
            Sair
          </button>
        </div>
      </header>

      <section className="search-section">
        <h2>Buscar questões</h2>

        <form className="search-form" onSubmit={handleSearch}>
          <div className="form-group">
            <label htmlFor="query">Termo de pesquisa</label>

            <input
              id="query"
              name="query"
              type="search"
              placeholder="Digite palavras-chave ou conteúdo da questão"
              value={filters.query || ""}
              onChange={handleFilterChange}
            />
          </div>

          <div className="search-filters">
            <div className="form-group">
              <label htmlFor="year">Ano</label>

              <input
                id="year"
                name="year"
                type="number"
                min="2004"
                max={new Date().getFullYear()}
                placeholder="Ex.: 2023"
                value={filters.year ?? ""}
                onChange={handleFilterChange}
              />
            </div>

            <div className="form-group">
              <label htmlFor="area">Área</label>

              <input
                id="area"
                name="area"
                type="text"
                placeholder="Área de conhecimento"
                value={filters.area || ""}
                onChange={handleFilterChange}
              />
            </div>

            <div className="form-group">
              <label htmlFor="discipline">Disciplina</label>

              <input
                id="discipline"
                name="discipline"
                type="text"
                placeholder="Disciplina"
                value={filters.discipline || ""}
                onChange={handleFilterChange}
              />
            </div>

            <div className="form-group">
              <label htmlFor="exam">Prova</label>

              <input
                id="exam"
                name="exam"
                type="text"
                placeholder="Tipo de prova"
                value={filters.exam || ""}
                onChange={handleFilterChange}
              />
            </div>

            <div className="form-group">
              <label htmlFor="institution">Instituição</label>

              <input
                id="institution"
                name="institution"
                type="text"
                placeholder="Instituição"
                value={filters.institution || ""}
                onChange={handleFilterChange}
              />
            </div>
          </div>

          <div className="search-actions">
            <button type="submit" disabled={isLoading}>
              {isLoading ? "Pesquisando..." : "Pesquisar"}
            </button>

            <button
              type="button"
              onClick={handleReset}
              disabled={isLoading}
            >
              Limpar filtros
            </button>
          </div>
        </form>
      </section>

      <section className="results-section">
        <div className="results-header">
          <h2>Resultados</h2>

          <span>
            {totalResults} questão(ões) encontrada(s)
          </span>
        </div>

        {error && (
          <div className="search-error" role="alert">
            {error}
          </div>
        )}

        {selectionError && (
          <div className="search-error" role="alert">
            {selectionError}
          </div>
        )}

        {isLoading ? (
          <p>Carregando questões...</p>
        ) : questions.length === 0 ? (
          <p>Nenhuma questão encontrada. Experimente outros filtros.</p>
        ) : (
          <div className="question-list">
            {questions.map((question) => {
              const questionId =
                question.questionId ||
                question.question_id ||
                question.id;

              const alreadySelected = isQuestionSelected(questionId);

              return (
                <article
                  className="question-card"
                  key={questionId}
                >
                  <div className="question-card-header">
                    <h3>
                      Questão {question.number || question.question_number || ""}
                    </h3>

                    <span>
                      {question.metadata?.year ||
                        question.year ||
                        "Ano não informado"}
                    </span>
                  </div>

                  <p className="question-statement">
                    {question.statement ||
                      question.question_text ||
                      question.statement_text ||
                      "Enunciado indisponível."}
                  </p>

                  <div className="question-metadata">
                    {(question.metadata?.area || question.area) && (
                      <span>
                        Área: {question.metadata?.area || question.area}
                      </span>
                    )}

                    {(question.metadata?.discipline ||
                      question.discipline) && (
                      <span>
                        Disciplina:{" "}
                        {question.metadata?.discipline ||
                          question.discipline}
                      </span>
                    )}
                  </div>

                  <div className="question-actions">
                    <button
                      type="button"
                      onClick={() =>
                        navigate(`/questions/${encodeURIComponent(questionId)}`)
                      }
                    >
                      Ver questão
                    </button>

                    <button
                      type="button"
                      onClick={() => handleAddQuestion(questionId)}
                      disabled={
                        alreadySelected ||
                        selectedQuestionId === questionId
                      }
                    >
                      {alreadySelected
                        ? "Adicionada"
                        : selectedQuestionId === questionId
                          ? "Adicionando..."
                          : "Adicionar à seleção"}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}

        {totalPages > 1 && (
          <nav className="pagination" aria-label="Paginação dos resultados">
            <button
              type="button"
              onClick={() => previousPage()}
              disabled={currentPage === 0 || isLoading}
            >
              Anterior
            </button>

            <span>
              Página {currentPage + 1} de {totalPages}
            </span>

            <button
              type="button"
              onClick={() => nextPage()}
              disabled={currentPage + 1 >= totalPages || isLoading}
            >
              Próxima
            </button>
          </nav>
        )}
      </section>
    </main>
  );
}

export default SearchView;