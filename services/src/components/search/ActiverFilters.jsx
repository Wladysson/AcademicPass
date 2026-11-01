const FILTER_LABELS = {
  year: "Ano",
  area: "Área",
  discipline: "Disciplina",
  exam: "Prova",
  institution: "Instituição",
};

export default function ActiveFilters({
  filters = {},
  onRemoveFilter,
  onClearFilters,
}) {
  const activeFilters = Object.entries(filters).filter(
    ([name, value]) =>
      Object.prototype.hasOwnProperty.call(FILTER_LABELS, name) &&
      value !== undefined &&
      value !== null &&
      value !== ""
  );

  if (activeFilters.length === 0) {
    return null;
  }

  function handleRemove(name) {
    if (typeof onRemoveFilter === "function") {
      onRemoveFilter(name);
    }
  }

  function handleClear() {
    if (typeof onClearFilters === "function") {
      onClearFilters();
    }
  }

  return (
    <section
      className="active-filters"
      aria-label="Filtros aplicados"
    >
      <div className="active-filters__header">
        <h2>Filtros aplicados</h2>

        <button
          type="button"
          className="active-filters__clear"
          onClick={handleClear}
        >
          Limpar todos
        </button>
      </div>

      <div className="active-filters__list">
        {activeFilters.map(([name, value]) => (
          <span
            key={name}
            className="active-filters__item"
          >
            <span className="active-filters__label">
              {FILTER_LABELS[name]}:
            </span>

            <span className="active-filters__value">
              {String(value)}
            </span>

            <button
              type="button"
              className="active-filters__remove"
              onClick={() => handleRemove(name)}
              aria-label={`Remover filtro ${FILTER_LABELS[name]}`}
              title={`Remover filtro ${FILTER_LABELS[name]}`}
            >
              ×
            </button>
          </span>
        ))}
      </div>
    </section>
  );
}
