import { useEffect, useState } from "react";
import { FileSearch, Search } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { searchCaseVault } from "../lib/api";
import Badge from "../components/Badge";
export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") || ""),
    [results, setResults] = useState([]),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");
  async function run(value = query) {
    if (!value.trim()) {
      setResults([]);
      return;
    }
    setLoading(true);
    setError("");
    setParams({ q: value.trim() });
    try {
      setResults(await searchCaseVault(value));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    const q = params.get("q");
    if (q) run(q);
  }, []);
  return (
    <div className="page">
      <div className="page-title-row">
        <div>
          <p className="eyebrow">Records index</p><h1>Case & Evidence Search</h1>
          <p>
            Search case records and extracted text. Results follow your case access and evidence clearance.
          </p>
        </div>
      </div>
      <form
        className="search-hero"
        onSubmit={(e) => {
          e.preventDefault();
          run();
        }}
      >
        <Search size={20} />
        <input
          aria-label="Search cases and evidence"
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search case numbers, titles, and extracted text…"
        />
        <button className="button button-primary">Search</button>
      </form>
      {error ? <div className="form-error">{error}</div> : null}
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>
              {loading
                ? "Searching…"
                : params.get("q")
                  ? `${results.length} results`
                  : "Search evidence"}
            </h2>
            <p>
              Matching evidence is indexed by case, source page, and text relevance.
            </p>
          </div>
        </div>
        {results.length ? (
          <div className="search-results">
            {results.map((r, i) => (
              <Link
                to={`/documents/${r.document_id}`}
                className="search-result"
                key={`${r.document_id}-${r.page_number}-${i}`}
              >
                <FileSearch size={18} />
                <div className="grow">
                  <div className="search-result-title">
                    <strong>{r.title}</strong>
                    <Badge>{r.case_number}</Badge>
                    {r.page_number ? (
                      <span className="muted small">page {r.page_number}</span>
                    ) : null}
                  </div>
                  <p>{r.snippet || "Document metadata match"}</p>
                </div>
                <span className="rank-label" title="Text relevance score">
                  Relevance {Number(r.rank || 0).toFixed(2)}
                </span>
              </Link>
            ))}
          </div>
        ) : (
          <div className="panel-empty">
            {params.get("q") && !loading
              ? "No accessible matches."
              : "Enter a phrase to search."}
          </div>
        )}
      </section>
    </div>
  );
}
