import { useEffect, useId, useState } from "react";
import mermaid from "mermaid";

mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  theme: "default",
  flowchart: {
    htmlLabels: false,
    curve: "linear",
  },
  sequence: {
    useMaxWidth: true,
  },
});

export default function DiagramRenderer({
  diagram,
  title = "Diagrama",
  className = "",
  errorMessage = "Não foi possível renderizar este diagrama.",
}) {
  const generatedId = useId();
  const [renderedSvg, setRenderedSvg] = useState("");
  const [error, setError] = useState(null);

  const source =
    typeof diagram === "string"
      ? diagram
      : diagram?.mermaid ??
        diagram?.content ??
        diagram?.source ??
        "";

  useEffect(() => {
    let active = true;

    async function renderDiagram() {
      const normalizedSource = source.trim();

      setRenderedSvg("");
      setError(null);

      if (!normalizedSource) {
        return;
      }

      try {
        const elementId = `mermaid-${generatedId.replace(
          /[^a-zA-Z0-9_-]/g,
          ""
        )}`;

        const result = await mermaid.render(
          elementId,
          normalizedSource
        );

        if (active) {
          setRenderedSvg(result.svg);
        }
      } catch {
        if (active) {
          setError(errorMessage);
        }
      }
    }

    renderDiagram();

    return () => {
      active = false;
    };
  }, [source, generatedId, errorMessage]);

  if (!source.trim()) {
    return null;
  }

  return (
    <figure className={`diagram-renderer ${className}`.trim()}>
      {title && (
        <figcaption className="diagram-renderer__title">
          {title}
        </figcaption>
      )}

      {error ? (
        <div
          className="diagram-renderer__error"
          role="alert"
        >
          <p>{error}</p>
        </div>
      ) : renderedSvg ? (
        <div
          className="diagram-renderer__content"
          role="img"
          aria-label={title || "Diagrama"}
          dangerouslySetInnerHTML={{
            __html: renderedSvg,
          }}
        />
      ) : (
        <div
          className="diagram-renderer__loading"
          role="status"
        >
          Preparando diagrama...
        </div>
      )}
    </figure>
  );
}
