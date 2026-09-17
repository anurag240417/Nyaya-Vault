import { useState } from "react";
import {
  CheckCircle2,
  Fingerprint,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { verifyIntegrity } from "../lib/api";
import { formatDate } from "../lib/format";
export default function IntegrityPage() {
  const { t } = useTranslation("integrity");
  const [result, setResult] = useState(null),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");
  async function verify() {
    setLoading(true);
    setError("");
    try {
      setResult(await verifyIntegrity());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="page">
      <div className="page-title-row">
        <div>
          <h1>{t("title")}</h1>
          <p>
            {t("subtitle")}
          </p>
        </div>
      </div>
      <section className="integrity-hero">
        <div className="integrity-icon">
          <Fingerprint size={42} />
        </div>
        <h2>{t("hero.title")}</h2>
        <p>
          {t("hero.description")}
        </p>
        <button
          className="button button-primary"
          disabled={loading}
          onClick={verify}
        >
          <ShieldCheck size={17} />{" "}
          {loading ? t("actions.verifying") : t("actions.verify")}
        </button>
      </section>
      {error ? <div className="form-error">{error}</div> : null}
      {result ? (
        <section
          role="status" className={`verification-card ${result.valid ? "valid" : "invalid"}`}
        >
          {result.valid ? (
            <CheckCircle2 size={34} />
          ) : (
            <TriangleAlert size={34} />
          )}
          <div>
            <h2>
              {result.valid
                ? t("result.valid")
                : t("result.invalid")}
            </h2>
            <p>{result.detail}</p>
            <div className="verification-meta">
              <span>
                <strong>{result.total_entries}</strong> {t("meta.entriesChecked")}
              </span>
              <span>
                <strong>{result.first_invalid_sequence || t("meta.noneFallback")}</strong> {t("meta.firstInvalid")}
              </span>
              <span>{t("meta.checked", { date: formatDate(new Date()) })}</span>
            </div>
          </div>
        </section>
      ) : null}
      <section className="panel">
        <div className="record-body">
          <h3>{t("scope.title")}</h3>
          <p>
            {t("scope.description")}
          </p>
        </div>
      </section>
    </div>
  );
}
