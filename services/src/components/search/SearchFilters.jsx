const FILTER_FIELDS = [
  {
    name: "year",
    label: "Ano",
    placeholder: "Todos os anos",
  },
  {
    name: "area",
    label: "Área",
    placeholder: "Todas as áreas",
  },
  {
    name: "discipline",
    label: "Disciplina",
    placeholder: "Todas as disciplinas",
  },
  {
    name: "exam",
    label: "Prova",
    placeholder: "Todas as provas",
  },
  {
    name: "institution",
    label: "Instituição",
    placeholder: "Todas as instituições",
  },
];

export default function SearchFilters({
  filters = {},
  options = {},
  onFilterChange,
  onReset,
  isLoading = false,
}) {
  function handleChange(event) {
    const { name, value } = event.target;

    if (typeof onFilterChange === "function") {
      onFilterChange(name, value);
    }
  }

  function handleReset() {
    if (typeof onReset === "function") {
      onReset();
    }
  }

  const hasActiveFilters = FILTER_FIELDS.some(({ name }) => {
    const value = filters[name];

    return value !== undefined && value !== null && value !== "";
  });

  return (
    <section
      className="search-filters"
      aria-label="Filtros de pesquisa"
    >
      <div className="search-filters__header">
        <div>
          <h2>Filtros</h2>
          <p>Refine sua pesquisa de questões.</p>
        </div>

        <button
          type="button"
          className="search-filters__reset"
          onClick={handleReset}
          disabled={isLoading || !hasActiveFilters}
        >
          Limpar filtros
        </button>
      </div>

      <div className="search-filters__fields">
        {FILTER_FIELDS.map((field) => {
          const fieldOptions = options[field.name] ?? [];

          return (
            <div
              className="search-filters__field"
              key={field.name}
            >
              <label htmlFor={`filter-${field.name}`}>
                {field.label}
              </label>

              <select
                id={`filter-${field.name}`}
                name={field.name}
                value={filters[field.name] ?? ""}
                onChange={handleChange}
                disabled={isLoading}
              >
                <option value="">
                  {field.placeholder}
                </option>

                {fieldOptions.map((option) => {
                  const value =
                    typeof option === "object"
                      ? option.value
                      : option;

                  const label =
                    typeof option === "object"
                      ? option.label
                      : option;

                  return (
                    <option
                      key={value}
                      value={value}
                    >
                      {label}
                    </option>
                  );
                })}
              </select>
            </div>
          );
        })}
      </div>
    </section>
  );
}
