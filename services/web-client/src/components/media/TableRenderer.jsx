function normalizeCell(cell) {
  if (cell === null || cell === undefined) {
    return "";
  }

  if (typeof cell === "object") {
    return String(
      cell.text ??
      cell.content ??
      cell.value ??
      ""
    );
  }

  return String(cell);
}

function normalizeTable(table) {
  if (Array.isArray(table)) {
    return {
      headers: [],
      rows: table,
    };
  }

  if (!table || typeof table !== "object") {
    return {
      headers: [],
      rows: [],
    };
  }

  const headers = Array.isArray(table.headers)
    ? table.headers
    : Array.isArray(table.columns)
      ? table.columns
      : [];

  const rows = Array.isArray(table.rows)
    ? table.rows
    : Array.isArray(table.data)
      ? table.data
      : [];

  return {
    headers,
    rows,
  };
}

export default function TableRenderer({
  table,
  title = "Tabela",
  showTitle = true,
  className = "",
  emptyMessage = "Não há dados disponíveis para esta tabela.",
}) {
  const normalizedTable = normalizeTable(table);

  const headers = normalizedTable.headers.map(normalizeCell);

  const rows = normalizedTable.rows
    .filter((row) => Array.isArray(row))
    .map((row) => row.map(normalizeCell));

  const hasContent =
    headers.length > 0 ||
    rows.some((row) => row.length > 0);

  if (!hasContent) {
    return (
      <div
        className={`table-renderer table-renderer--empty ${className}`.trim()}
      >
        <p>{emptyMessage}</p>
      </div>
    );
  }

  return (
    <figure className={`table-renderer ${className}`.trim()}>
      {showTitle && title && (
        <figcaption className="table-renderer__title">
          {title}
        </figcaption>
      )}

      <div className="table-renderer__container">
        <table className="table-renderer__table">
          {headers.length > 0 && (
            <thead>
              <tr>
                {headers.map((header, index) => (
                  <th key={index} scope="col">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
          )}

          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}
