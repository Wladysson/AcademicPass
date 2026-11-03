
import { useState } from "react";

export default function SearchBar({
  initialValue = "",
  onSearch,
  isLoading = false,
  placeholder = "Pesquise por enunciado, conteúdo ou palavra-chave...",
}) {
  const [query, setQuery] = useState(initialValue);

  function handleSubmit(event) {
    event.preventDefault();

    const normalizedQuery = query.trim();

    if (isLoading || typeof onSearch !== "function") {
      return;
    }

    onSearch(normalizedQuery);
  }

  function handleClear() {
    setQuery("");

    if (typeof onSearch === "function") {
      onSearch("");
    }
  }

  return (
    <form
      className="search-bar"
      onSubmit={handleSubmit}
      role="search"
    >
      <label
        htmlFor="question-search"
        className="search-bar__label"
      >
        Pesquisar questões
      </label>

      <div className="search-bar__container">
        <input
          id="question-search"
          type="search"
          className="search-bar__input"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={placeholder}
          aria-label="Termo de pesquisa das questões"
          autoComplete="off"
        />

        {query && (
          <button
            type="button"
            className="search-bar__clear"
            onClick={handleClear}
            disabled={isLoading}
            aria-label="Limpar pesquisa"
          >
            Limpar
          </button>
        )}

        <button
          type="submit"
          className="search-bar__submit"
          disabled={isLoading}
        >
          {isLoading ? "Pesquisando..." : "Pesquisar"}
        </button>
      </div>
    </form>
  );
}
