export default function SearchPagination({
  currentPage = 0,
  pageSize = 20,
  totalResults = 0,
  onPageChange,
  isLoading = false,
}) {
  const totalPages = Math.ceil(totalResults / pageSize);

  if (totalPages <= 1) {
    return null;
  }

  const firstPage = 0;
  const lastPage = totalPages - 1;

  const startResult = currentPage * pageSize + 1;
  const endResult = Math.min(
    (currentPage + 1) * pageSize,
    totalResults
  );

  function handlePageChange(page) {
    if (
      isLoading ||
      typeof onPageChange !== "function" ||
      page < firstPage ||
      page > lastPage ||
      page === currentPage
    ) {
      return;
    }

    onPageChange(page);
  }

  function getVisiblePages() {
    const maxVisiblePages = 5;
    const halfRange = Math.floor(maxVisiblePages / 2);

    let start = Math.max(0, currentPage - halfRange);
    let end = Math.min(
      totalPages - 1,
      start + maxVisiblePages - 1
    );

    start = Math.max(0, end - maxVisiblePages + 1);

    return Array.from(
      { length: end - start + 1 },
      (_, index) => start + index
    );
  }

  return (
    <nav
      className="search-pagination"
      aria-label="Paginação dos resultados"
    >
      <div className="search-pagination__info">
        <span>
          Exibindo {startResult}–{endResult} de {totalResults} questões
        </span>
      </div>

      <div className="search-pagination__controls">
        <button
          type="button"
          className="search-pagination__navigation"
          onClick={() => handlePageChange(firstPage)}
          disabled={isLoading || currentPage === firstPage}
          aria-label="Ir para a primeira página"
        >
          Primeira
        </button>

        <button
          type="button"
          className="search-pagination__navigation"
          onClick={() => handlePageChange(currentPage - 1)}
          disabled={isLoading || currentPage === firstPage}
          aria-label="Página anterior"
        >
          Anterior
        </button>

        {getVisiblePages().map((page) => (
          <button
            key={page}
            type="button"
            className={`search-pagination__page ${
              page === currentPage
                ? "search-pagination__page--active"
                : ""
            }`}
            onClick={() => handlePageChange(page)}
            disabled={isLoading || page === currentPage}
            aria-label={`Página ${page + 1}`}
            aria-current={
              page === currentPage ? "page" : undefined
            }
          >
            {page + 1}
          </button>
        ))}

        <button
          type="button"
          className="search-pagination__navigation"
          onClick={() => handlePageChange(currentPage + 1)}
          disabled={isLoading || currentPage === lastPage}
          aria-label="Próxima página"
        >
          Próxima
        </button>

        <button
          type="button"
          className="search-pagination__navigation"
          onClick={() => handlePageChange(lastPage)}
          disabled={isLoading || currentPage === lastPage}
          aria-label="Ir para a última página"
        >
          Última
        </button>
      </div>
    </nav>
  );
}
