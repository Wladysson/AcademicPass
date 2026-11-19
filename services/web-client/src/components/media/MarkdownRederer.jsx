import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function MarkdownRenderer({
  content,
  className = "",
  emptyMessage = "Nenhum conteúdo disponível.",
}) {
  const markdown = typeof content === "string"
    ? content.trim()
    : "";

  if (!markdown) {
    return (
      <div className={`markdown-renderer markdown-renderer--empty ${className}`.trim()}>
        <p>{emptyMessage}</p>
      </div>
    );
  }

  return (
    <article className={`markdown-renderer ${className}`.trim()}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ children, href, ...props }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                {...props}
              >
                {children}
              </a>
            );
          },

          table({ children }) {
            return (
              <div className="markdown-renderer__table-container">
                <table>{children}</table>
              </div>
            );
          },

          pre({ children }) {
            return (
              <pre className="markdown-renderer__code-block">
                {children}
              </pre>
            );
          },

          img({ src, alt, ...props }) {
            return (
              <img
                src={src}
                alt={alt ?? ""}
                loading="lazy"
                {...props}
              />
            );
          },
        }}
      >
        {markdown}
      </ReactMarkdown>
    </article>
  );
}
