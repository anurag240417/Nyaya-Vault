import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const components = {
  h1: ({ children }) => <h3>{children}</h3>,
  h2: ({ children }) => <h4>{children}</h4>,
  h3: ({ children }) => <h4>{children}</h4>,
  table: ({ children }) => (
    <div className="response-table" role="region" aria-label="Response table" tabIndex={0}>
      <table>{children}</table>
    </div>
  ),
};

// Render generated text as structured content, never executable HTML.
export default function AssistantResponse({ children }) {
  return (
    <div className="assistant-response">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components} skipHtml
        disallowedElements={["img"]}>
        {children || ""}
      </ReactMarkdown>
    </div>
  );
}
