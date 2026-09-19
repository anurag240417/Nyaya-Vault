import { useEffect, useState } from "react";
import {
  CheckCircle2,
  Fingerprint,
  Link2,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  createIntegrityAnchor,
  listIntegrityAnchors,
  verifyIntegrity,
  verifyIntegrityAnchor,
} from "../lib/api";
import { formatDate, shortHash } from "../lib/format";
import { useAuth } from "../context/AuthContext";
import Toast from "../components/Toast";

function statusBadgeClass(status) {
  if (status === "CONFIRMED") return "badge-success";
  if (status === "FAILED") return "badge-danger";
  return "badge-warning";
}

export default function IntegrityPage() {
  const { t } = useTranslation("integrity");
  const { profile } = useAuth();
  const isAdmin = profile?.role === "ADMIN";

  const [result, setResult] = useState(null),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");

  const [anchorState, setAnchorState] = useState({ enabled: false, schedule: null, anchors: [] });
  const [anchoring, setAnchoring] = useState(false);
  const [verifyingId, setVerifyingId] = useState(null);
  const [verifications, setVerifications] = useState({});
  const [toast, setToast] = useState(null);

  async function loadAnchors() {
    try {
      setAnchorState(await listIntegrityAnchors());
    } catch (e) {
      setToast({ type: "error", message: e.message });
    }
  }

  useEffect(() => {
    loadAnchors();
  }, []);

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

  async function anchorNow() {
    setAnchoring(true);
    try {
      const anchor = await createIntegrityAnchor();
      setToast({ message: t("anchors.created", { hash: shortHash(anchor.tx_hash, 12) }) });
      await loadAnchors();
    } catch (e) {
      setToast({ type: "error", message: e.message });
    } finally {
      setAnchoring(false);
    }
  }

  async function verifyAnchor(anchorId) {
    setVerifyingId(anchorId);
    try {
      const outcome = await verifyIntegrityAnchor(anchorId);
      setVerifications((prev) => ({ ...prev, [anchorId]: outcome }));
    } catch (e) {
      setToast({ type: "error", message: e.message });
    } finally {
      setVerifyingId(null);
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
        <div className="panel-header">
          <h2><Link2 size={17} /> {t("anchors.title")}</h2>
          {isAdmin ? (
            <button className="button button-official" disabled={anchoring} onClick={anchorNow}>
              <Link2 size={15} /> {anchoring ? t("anchors.anchoring") : t("anchors.anchorNow")}
            </button>
          ) : null}
        </div>
        <div className="record-body">
          <p className="muted small">
            {anchorState.enabled ? t("anchors.description") : t("anchors.notConfigured")}
          </p>
          {anchorState.schedule?.enabled ? (
            <p className="muted small">
              {t("anchors.schedule.on", { minutes: Math.max(1, Math.round(anchorState.schedule.interval_seconds / 60)) })}
              {anchorState.schedule.last_result ? (
                <>
                  {" "}
                  {t("anchors.schedule.last", {
                    when: formatDate(anchorState.schedule.last_run_at),
                    result: t(`anchors.schedule.results.${anchorState.schedule.last_result.status}`),
                  })}
                </>
              ) : null}
            </p>
          ) : null}
        </div>
        {anchorState.anchors.length ? (
          <div className="anchor-register data-list">
            <div className="data-header">
              <span>{t("anchors.columns.sequence")}</span>
              <span>{t("anchors.columns.status")}</span>
              <span>{t("anchors.columns.reference")}</span>
              <span>{t("anchors.columns.network")}</span>
              <span>{t("anchors.columns.anchoredAt")}</span>
              <span>{t("anchors.columns.verify")}</span>
            </div>
            {anchorState.anchors.map((anchor) => {
              const outcome = verifications[anchor.id];
              return (
                <div className="data-row" key={anchor.id}>
                  <code>#{anchor.audit_sequence}</code>
                  <span className={`badge ${statusBadgeClass(anchor.tx_status)}`}>{anchor.tx_status}</span>
                  {anchor.explorer_url ? (
                    <a href={anchor.explorer_url} target="_blank" rel="noreferrer">
                      {shortHash(anchor.anchor_reference, 14)}
                    </a>
                  ) : (
                    <code>{shortHash(anchor.anchor_reference, 14)}</code>
                  )}
                  <span>{anchor.anchor_provider}</span>
                  <span className="small">{formatDate(anchor.anchored_at)}</span>
                  <span>
                    <button
                      className="button button-sm"
                      disabled={verifyingId === anchor.id}
                      onClick={() => verifyAnchor(anchor.id)}
                    >
                      {verifyingId === anchor.id ? t("anchors.verifying") : t("anchors.verifyAction")}
                    </button>
                    {outcome ? (
                      <span className={`badge ${outcome.verified ? "badge-success" : "badge-danger"}`} style={{ marginLeft: 8 }}>
                        {outcome.verified ? (
                          <><ShieldCheck size={11} /> {t("anchors.verified")}</>
                        ) : (
                          <><ShieldAlert size={11} /> {t("anchors.tampered")}</>
                        )}
                      </span>
                    ) : null}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="panel-empty">
            <span>{t("anchors.empty")}</span>
          </div>
        )}
      </section>

      <section className="panel">
        <div className="record-body">
          <h3>{t("scope.title")}</h3>
          <p>
            {t("scope.description")}
          </p>
        </div>
      </section>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
