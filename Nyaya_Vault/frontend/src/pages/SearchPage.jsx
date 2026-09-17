import { useEffect, useState } from "react";
import { FileSearch, Search } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { searchCaseVault } from "../lib/api";
import Badge from "../components/Badge";
export default function SearchPage() {
  const { t } = useTranslation("search");
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
          <p className="eyebrow">{t("eyebrow")}</p><h1>{t("title")}</h1>
          <p>
            {t("subtitle")}
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
          aria-label={t("inputAria")}
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("inputPlaceholder")}
        />
        <button className="button button-primary">{t("actions.search")}</button>
      </form>
      {error ? <div className="form-error">{error}</div> : null}
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>
              {loading
                ? t("status.searching")
                : params.get("q")
                  ? t("status.resultsCount", { count: results.length })
                  : t("status.prompt")}
            </h2>
            <p>
              {t("resultsHint")}
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
                      <span className="muted small">{t("pageLabel", { number: r.page_number })}</span>
                    ) : null}
                  </div>
                  <p>{r.snippet || t("metadataMatchFallback")}</p>
                </div>
                <span className="rank-label" title={t("relevanceScoreTitle")}>
                  {t("relevanceLabel", { score: Number(r.rank || 0).toFixed(2) })}
                </span>
              </Link>
            ))}
          </div>
        ) : (
          <div className="panel-empty">
            {params.get("q") && !loading
              ? t("empty.noMatches")
              : t("empty.prompt")}
          </div>
        )}
      </section>
    </div>
  );
}
