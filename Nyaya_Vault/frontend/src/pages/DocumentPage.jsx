import DocumentKindIcon from "../components/DocumentKindIcon";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowLeft,
  ScanLine,
  Check,
  Download,
  FileClock,
  FileOutput,
  Plus,
  RefreshCw,
  ScanSearch,
  ShieldAlert,
  X,
} from "lucide-react";
import Badge, { clearanceTone } from "../components/Badge";
import LoadingState from "../components/LoadingState";
import Modal from "../components/Modal";
import CertificateModal from "../components/CertificateModal";
import Toast from "../components/Toast";
import {
  confirmEntities,
  confirmRedactions,
  downloadDocumentVersion,
  getDocument,
  getEntities,
  getLatestVersionData,
  getRedactions,
  listDocumentVersions,
  uploadDocumentVersion,
  getVersionObjectUrl,
} from "../lib/api";
import { formatBytes, formatDate, shortHash } from "../lib/format";
import {
  exportRedactedDocument,
  isProcessorConfigured,
  requestDocumentProcessing,
} from "../lib/processor";
export default function DocumentPage() {
  const { t } = useTranslation("documentPage");
  const { documentId } = useParams();
  const [doc, setDoc] = useState(null),
    [versions, setVersions] = useState([]),
    [latest, setLatest] = useState(null),
    [entities, setEntities] = useState([]),
    [redactions, setRedactions] = useState([]),
    [tab, setTab] = useState("overview"),
    [loading, setLoading] = useState(true),
    [toast, setToast] = useState(null),
    [versionModal, setVersionModal] = useState(false),
    [certModal, setCertModal] = useState(false),
    [versionForm, setVersionForm] = useState({ file: null, changeSummary: "" }),
    [busy, setBusy] = useState(false);
  const reload = useCallback(async () => {
    const d = await getDocument(documentId);
    const vs = await listDocumentVersions(documentId);
    const l =
      vs.find((v) => v.version_number === d.current_version_number) ||
      (await getLatestVersionData(d));
    const [es, rs] = await Promise.all([
      getEntities(l.id),
      getRedactions(l.id),
    ]);
    setDoc(d);
    setVersions(vs);
    setLatest(l);
    setEntities(es);
    setRedactions(rs);
  }, [documentId]);
  useEffect(() => {
    reload()
      .catch((e) => setToast({ type: "error", message: e.message }))
      .finally(() => setLoading(false));
  }, [reload]);
  if (loading) return <LoadingState label={t("loading.evidence")} />;
  if (!doc)
    return (
      <div className="center-message">
        <h2>{t("documentUnavailable")}</h2>
      </div>
    );
  async function addVersion(e) {
    e.preventDefault();
    if (!versionForm.file) return;
    setBusy(true);
    try {
      await uploadDocumentVersion({ document: doc, ...versionForm });
      setVersionModal(false);
      setVersionForm({ file: null, changeSummary: "" });
      await reload();
      setToast({ message: t("toast.versionCreated") });
    } catch (err) {
      setToast({ type: "error", message: err.message });
    } finally {
      setBusy(false);
    }
  }
  async function runProcessor() {
    if (!latest) return;
    setBusy(true);
    try {
      await requestDocumentProcessing({ documentId, versionId: latest.id });
      setToast({ message: t("toast.processingAccepted") });
      setTimeout(() => reload().catch(() => {}), 1000);
    } catch (err) {
      setToast({ type: "error", message: err.message });
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page document-page">
      <Link className="back-link" to={`/cases/${doc.case_id}/documents`} data-guide="doc-back">
        <ArrowLeft size={15} /> {t("backToRegister")}
      </Link>
      <div className="document-title-row">
        <div className="document-icon">
          <DocumentKindIcon doc={{ ...doc, mime_type: latest?.mime_type ?? versions[0]?.mime_type }} size={28} />
        </div>
        <div className="grow">
          <p className="eyebrow">{t("eyebrow")}</p>
          <div className="title-with-badges">
            <h1>{doc.title}</h1>
            <Badge tone={clearanceTone(doc.clearance_level)} data-guide="clearance-badge">
              {doc.clearance_level}
            </Badge>
          </div>
          <p>
            {t("typeVersion", {
              type: doc.document_type || t("unclassifiedDocument"),
              version: doc.current_version_number,
            })}
          </p>
        </div>
        <button className="button" data-guide="doc-new-version" onClick={() => setVersionModal(true)}>
          <Plus size={16} /> {t("actions.newVersion")}
        </button>
        {latest ? (
          <button
            className="button"
            data-guide="doc-download"
            onClick={() =>
              downloadDocumentVersion(documentId, latest).catch((e) =>
                setToast({ type: "error", message: e.message }),
              )
            }
          >
            <Download size={16} /> {t("actions.download")}
          </button>
        ) : null}
        {latest ? (
          <button className="button button-official" data-guide="doc-certificate" onClick={() => setCertModal(true)}>
            <FileOutput size={16} /> {t("actions.certificate")}
          </button>
        ) : null}
      </div>
      <nav className="subtabs">
        {["overview", "entities", "redactions", "versions"].map((v) => (
          <button
            key={v}
            data-guide={`doc-tab-${v}`}
            aria-pressed={tab === v} className={tab === v ? "active" : ""}
            onClick={() => setTab(v)}
          >
            {{ overview: t("tabs.overview"), entities: t("tabs.entities"), redactions: t("tabs.redactions"), versions: t("tabs.versions") }[v]}
            {v === "entities" ? (
              <span className="counter">{entities.length}</span>
            ) : v === "redactions" ? (
              <span className="counter">{redactions.length}</span>
            ) : v === "versions" ? (
              <span className="counter">{versions.length}</span>
            ) : null}
          </button>
        ))}
      </nav>
      {tab === "overview" ? (
        <Overview
          documentId={documentId}
          doc={doc}
          latest={latest}
          runProcessor={runProcessor}
          busy={busy}
        />
      ) : null}
      {tab === "entities" ? (
        <Entities
          documentId={documentId}
          entities={entities}
          reload={reload}
          setToast={setToast}
        />
      ) : null}
      {tab === "redactions" ? (
        <Redactions
          documentId={documentId}
          documentTitle={doc.title}
          redactions={redactions}
          reload={reload}
          setToast={setToast}
          runProcessor={runProcessor}
          busy={busy}
        />
      ) : null}
      {tab === "versions" ? (
        <Versions
          documentId={documentId}
          versions={versions}
          setToast={setToast}
        />
      ) : null}
      {versionModal ? (
        <Modal
          title={t("modal.newVersionTitle")}
          onClose={() => setVersionModal(false)}
          footer={
            <>
              <button className="button" onClick={() => setVersionModal(false)}>
                {t("actions.cancel")}
              </button>
              <button
                form="new-version"
                className="button button-primary"
                disabled={busy}
              >
                {busy ? t("loading.uploading") : t("actions.createVersion")}
              </button>
            </>
          }
        >
          <form id="new-version" className="form-stack" onSubmit={addVersion}>
            <label className="field">
              <span>{t("modal.changeSummary")}</span>
              <input
                required
                maxLength="500"
                value={versionForm.changeSummary}
                onChange={(e) =>
                  setVersionForm({
                    ...versionForm,
                    changeSummary: e.target.value,
                  })
                }
              />
            </label>
            <label className="field">
              <span>{t("modal.file")}</span>
              <input
                required
                type="file"
                accept="application/pdf,image/jpeg,image/png,image/tiff,video/mp4,video/quicktime,video/webm"
                onChange={(e) =>
                  setVersionForm({
                    ...versionForm,
                    file: e.target.files?.[0] || null,
                  })
                }
              />
            </label>
          </form>
        </Modal>
      ) : null}
      {certModal && latest ? (
        <CertificateModal
          documentId={documentId}
          versionId={latest.id}
          onClose={() => setCertModal(false)}
        />
      ) : null}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
function Overview({ documentId, doc, latest, runProcessor, busy }) {
  const { t } = useTranslation("documentPage");
  const configured = isProcessorConfigured();
  const mimeType = latest?.mime_type || "";
  const isVideo = mimeType.startsWith("video/");
  const isImage = mimeType.startsWith("image/");
  const isPdf = mimeType === "application/pdf";
  const isPreviewable = isVideo || isImage || isPdf;
  const [previewUrl, setPreviewUrl] = useState(null);
  const [previewError, setPreviewError] = useState(null);
  useEffect(() => {
    if (!isPreviewable || !latest) {
      setPreviewUrl(null);
      setPreviewError(null);
      return;
    }
    let cancelled = false,
      objectUrl = null;
    setPreviewUrl(null);
    setPreviewError(null);
    getVersionObjectUrl(documentId, latest)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setPreviewUrl(url);
      })
      .catch((e) => {
        if (!cancelled) setPreviewError(e.message);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [isPreviewable, documentId, latest]);
  return (
    <div className="two-column evidence-layout">
      <section className="panel">
        <div className="panel-header" data-guide="doc-preview">
          <div>
            <h2>{t("overview.sourceEvidence")}</h2>
            <p>{t("overview.sha256Note")}</p>
          </div>
        </div>
        {isPreviewable ? (
          <div className="evidence-preview">
            {previewError ? (
              <p className="form-error">
                {t("overview.previewError", { error: previewError })}
              </p>
            ) : !previewUrl ? (
              <LoadingState label={t("loading.preview")} />
            ) : isVideo ? (
              <video
                controls
                preload="metadata"
                src={previewUrl}
              />
            ) : isImage ? (
              <img
                src={previewUrl}
                alt={doc.title}
              />
            ) : isPdf ? (
              <embed
                title={t("overview.embedTitle", { title: doc.title })}
                src={previewUrl}
                type="application/pdf"
              />
            ) : null}
          </div>
        ) : <div className="panel-empty">{t("overview.noPreview")}</div>}

      </section>
      <aside className="stack">
        <section className="panel"><div className="panel-header"><h2>{t("overview.recordInformation")}</h2></div>
        <dl className="definition-grid">
          <dt>{t("overview.documentId")}</dt>
          <dd>
            <code>{doc.id}</code>
          </dd>
          <dt>{t("overview.type")}</dt>
          <dd>{doc.document_type || "—"}</dd>
          <dt>{t("overview.clearance")}</dt>
          <dd><Badge tone={clearanceTone(doc.clearance_level)}>{doc.clearance_level}</Badge></dd>
          <dt>{t("overview.department")}</dt><dd>{doc.department || t("overview.generalDepartment")}</dd>
          <dt>{t("overview.created")}</dt>
          <dd>{formatDate(doc.created_at)}</dd>
          <dt>{t("overview.currentVersion")}</dt>
          <dd>v{doc.current_version_number}</dd>
          {latest ? (
            <>
              <dt>{t("overview.sha256")}</dt>
              <dd data-guide="doc-hash">
                <code className="wrap-code">{latest.sha256}</code>
              </dd>
              <dt>{t("overview.size")}</dt>
              <dd>{formatBytes(latest.size_bytes)}</dd>
              <dt>{t("overview.mimeType")}</dt>
              <dd>{latest.mime_type}</dd>
            </>
          ) : null}
        </dl>
        </section>
        <section className="panel compact-panel" data-guide="doc-provenance">
          <h3>{t("overview.processingProvenance")}</h3>
          <ol className="provenance-sequence">
            <li><span>{t("overview.registration")}</span><strong>{t("overview.versionLabel", { number: doc.current_version_number })}</strong><small>{formatDate(latest?.created_at || doc.created_at)}</small></li>
            <li><span>{t("overview.fileFingerprint")}</span><strong>{latest?.sha256 ? t("overview.hashRecorded") : t("overview.noHash")}</strong></li>
            <li><span>{t("overview.processingRecord")}</span><strong>{latest?.processing_status || t("overview.noStatus")}</strong></li>
          </ol>
          {latest ? (
            <div className="processing-status">
              <Badge
                tone={
                  latest.processing_status === "READY"
                    ? "success"
                    : latest.processing_status === "FAILED"
                      ? "danger"
                      : "info"
                }
              >
                {latest.processing_status}
              </Badge>
              <span>
                {latest.ocr_used === true
                  ? t("overview.ocrUsed")
                  : latest.ocr_used === false
                    ? t("overview.nativeText")
                    : t("overview.extractionPending")}
              </span>
            </div>
          ) : null}
          {latest?.processing_error ? (
            <p className="form-error">{latest.processing_error}</p>
          ) : null}
          {isVideo ? (
            <p className="muted small">
              {t("overview.videoNote")}
            </p>
          ) : (
            <button
              className="button button-block"
              data-guide="doc-run-processing"
              disabled={!configured || busy}
              onClick={runProcessor}
            >
              <ScanLine size={16} />{" "}
              {busy ? t("loading.requesting") : t("actions.runProcessing")}
            </button>
          )}
        </section>
        <section className="panel compact-panel">
          <h3>{t("overview.humanConfirmation")}</h3>
          <p className="muted">
            {t("overview.humanConfirmationNote")}
          </p>
        </section>
      </aside>
    </div>
  );
}
function Entities({ documentId, entities, reload, setToast }) {
  const { t } = useTranslation("documentPage");
  const [choices, setChoices] = useState({});
  useEffect(
    () =>
      setChoices(
        Object.fromEntries(
          entities.map((e) => [e.id, e.confirmed ? "confirm" : "pending"]),
        ),
      ),
    [entities],
  );
  const dirty = useMemo(
    () =>
      entities.some(
        (e) =>
          choices[e.id] === "reject" ||
          (choices[e.id] === "confirm" && !e.confirmed),
      ),
    [entities, choices],
  );
  async function save() {
    const confirmed = Object.entries(choices)
      .filter(([, v]) => v === "confirm")
      .map(([id]) => id);
    const rejected = Object.entries(choices)
      .filter(([, v]) => v === "reject")
      .map(([id]) => id);
    try {
      await confirmEntities(documentId, confirmed, rejected);
      await reload();
      setToast({ message: t("toast.entityReviewSaved") });
    } catch (e) {
      setToast({ type: "error", message: e.message });
    }
  }
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>{t("entities.title")}</h2>
          <p>{t("entities.description")}</p>
        </div>
        <button
          className="button button-primary"
          data-guide="entity-save"
          disabled={!dirty}
          onClick={save}
        >
          <Check size={16} /> {t("actions.saveReview")}
        </button>
      </div>
      {entities.length ? (
        <div className="entity-list">
          {entities.map((e) => (
            <div className="entity-row" key={e.id}>
              <Badge tone="info">{e.entity_type}</Badge>
              <div className="grow">
                <strong>{e.value}</strong>
                <span className="muted small">
                  {t("entities.confidence", {
                    value:
                      e.confidence == null
                        ? "—"
                        : `${Math.round(e.confidence * 100)}%`,
                  })}
                </span>
              </div>
              <p className="review-state">{choices[e.id] === "confirm" ? (e.confirmed ? t("entities.stateConfirmed") : t("entities.stateConfirmUnsaved")) : choices[e.id] === "reject" ? t("entities.stateRejectUnsaved") : t("entities.statePending")}</p>
              <div className="review-toggle" data-guide="entity-decision">
                <button
                  aria-pressed={choices[e.id] === "confirm"} className={choices[e.id] === "confirm" ? "selected good" : ""}
                  onClick={() => setChoices({ ...choices, [e.id]: "confirm" })}
                >
                  <Check size={15} /> {t("actions.confirm")}
                </button>
                <button
                  aria-pressed={choices[e.id] === "reject"} className={choices[e.id] === "reject" ? "selected bad" : ""}
                  onClick={() => setChoices({ ...choices, [e.id]: "reject" })}
                >
                  <X size={15} /> {t("actions.reject")}
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="panel-empty">
          <ScanSearch size={20} /> {t("entities.empty")}
        </div>
      )}
    </section>
  );
}
function Redactions({
  documentId,
  documentTitle,
  redactions,
  reload,
  setToast,
  runProcessor,
  busy,
}) {
  const { t } = useTranslation("documentPage");
  const [choices, setChoices] = useState({});
  useEffect(
    () =>
      setChoices(
        Object.fromEntries(
          redactions.map((r) => [r.id, r.approved ? "approve" : "pending"]),
        ),
      ),
    [redactions],
  );
  async function save() {
    const approved = Object.entries(choices)
      .filter(([, v]) => v === "approve")
      .map(([id]) => id);
    const rejected = Object.entries(choices)
      .filter(([, v]) => v === "reject")
      .map(([id]) => id);
    try {
      await confirmRedactions(documentId, approved, rejected);
      await reload();
      setToast({ message: t("toast.redactionReviewSaved") });
    } catch (e) {
      setToast({ type: "error", message: e.message });
    }
  }
  async function exportCopy() {
    try {
      await exportRedactedDocument({
        documentId,
        filename: `${documentTitle.replace(/[^a-zA-Z0-9._-]/g, "_")}-redacted.pdf`,
      });
      setToast({ message: t("toast.redactedExported") });
    } catch (e) {
      setToast({ type: "error", message: e.message });
    }
  }
  const hasApproved = redactions.some(
    (r) => r.approved || choices[r.id] === "approve",
  );
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>{t("redactions.title")}</h2>
          <p>
            {t("redactions.description")}
          </p>
        </div>
        <div className="button-row">
          <button
            className="button"
            data-guide="redaction-generate"
            disabled={!isProcessorConfigured() || busy}
            onClick={runProcessor}
          >
            <RefreshCw size={16} /> {t("actions.generate")}
          </button>
          <button
            className="button"
            data-guide="redaction-export"
            disabled={!isProcessorConfigured() || !hasApproved || busy}
            onClick={exportCopy}
          >
            <FileOutput size={16} /> {t("actions.exportRedacted")}
          </button>
          <button
            className="button button-primary"
            data-guide="redaction-save"
            disabled={!redactions.length}
            onClick={save}
          >
            <Check size={16} /> {t("actions.saveReview")}
          </button>
        </div>
      </div>
      {redactions.length ? (
        <div className="entity-list">
          {redactions.map((r) => (
            <div className="entity-row" key={r.id}>
              <Badge tone="warning">{r.entity_type}</Badge>
              <div className="grow">
                <strong>{t("redactions.proposedRegion")}</strong>
                <code className="small wrap-code">
                  {JSON.stringify(r.region_json)}
                </code>
              </div>
              <p className="review-state">{choices[r.id] === "approve" ? (r.approved ? t("redactions.stateApproved") : t("redactions.stateApproveUnsaved")) : choices[r.id] === "reject" ? t("redactions.stateRejectUnsaved") : t("redactions.statePending")}</p>
              <div className="review-toggle" data-guide="redaction-decision">
                <button
                  aria-pressed={choices[r.id] === "approve"} className={choices[r.id] === "approve" ? "selected good" : ""}
                  onClick={() => setChoices({ ...choices, [r.id]: "approve" })}
                >
                  <Check size={15} /> {t("actions.approve")}
                </button>
                <button
                  aria-pressed={choices[r.id] === "reject"} className={choices[r.id] === "reject" ? "selected bad" : ""}
                  onClick={() => setChoices({ ...choices, [r.id]: "reject" })}
                >
                  <X size={15} /> {t("actions.reject")}
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="panel-empty">
          <ShieldAlert size={20} /> {t("redactions.empty")}
        </div>
      )}
    </section>
  );
}
function Versions({ documentId, versions, setToast }) {
  const { t } = useTranslation("documentPage");
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>{t("versions.title")}</h2>
          <p>{t("versions.description")}</p>
        </div>
      </div>
      <div className="version-list">
        {versions.map((v) => (
          <div className="version-row" key={v.id}>
            <span className="version-icon">
              <FileClock size={18} />
            </span>
            <div className="grow">
              <strong>{t("versions.versionLabel", { number: v.version_number })}</strong>
              <span>{v.change_summary || t("versions.noChangeSummary")}</span>
              <small className="muted">
                {formatDate(v.created_at)} · {formatBytes(v.size_bytes)} ·{" "}
                {shortHash(v.sha256, 14)}
              </small>
            </div>
            <Badge
              tone={
                v.processing_status === "READY"
                  ? "success"
                  : v.processing_status === "FAILED"
                    ? "danger"
                    : "info"
              }
            >
              {v.processing_status}
            </Badge>
            <button
              className="button button-sm"
              data-guide="version-download"
              onClick={() =>
                downloadDocumentVersion(documentId, v).catch((e) =>
                  setToast({ type: "error", message: e.message }),
                )
              }
            >
              <Download size={14} /> {t("actions.download")}
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
