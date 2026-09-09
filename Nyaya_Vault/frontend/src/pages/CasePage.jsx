import { useCallback, useEffect, useMemo, useState } from "react";
import { Route, Routes, useNavigate, useParams, Link } from "react-router-dom";
import {
  BriefcaseBusiness,
  FilePlus2,
  FileText,
  History,
  LockKeyhole,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";
import {
  addCollaborator,
  getCase,
  getCaseAudit,
  getCaseCollaborators,
  listCaseDocuments,
  listCollaboratorCandidates,
  removeCollaborator,
  uploadNewDocument,
} from "../lib/api";
import { formatDate, shortHash } from "../lib/format";
import { useAuth } from "../context/AuthContext";
import RepoTabs from "../components/RepoTabs";
import Badge, { clearanceTone } from "../components/Badge";
import Avatar from "../components/Avatar";
import Modal from "../components/Modal";
import EmptyState from "../components/EmptyState";
import LoadingState from "../components/LoadingState";
import Toast from "../components/Toast";
import { useRefreshOnFocus } from "../hooks/useRefreshOnFocus";
import {
  listTimelineStatements,
  listTimelineConflicts,
  addTimelineStatement,
  generateTimelineSuggestions,
  confirmTimelineSuggestion,
  rejectTimelineSuggestion,
} from "../lib/api";
export default function CasePage() {
  const { caseId } = useParams();
  const { profile } = useAuth();
  const [caseItem, setCaseItem] = useState(null),
    [documents, setDocuments] = useState([]),
    [collaborators, setCollaborators] = useState([]),
    [audit, setAudit] = useState([]),
    [statements, setStatements] = useState([]),
    [conflicts, setConflicts] = useState([]),
    [loading, setLoading] = useState(true),
    [toast, setToast] = useState(null);
  const reload = useCallback(async () => {
    const [c, d, co, a, st, cf] = await Promise.all([
      getCase(caseId),
      listCaseDocuments(caseId),
      getCaseCollaborators(caseId),
      getCaseAudit(caseId),
      listTimelineStatements(caseId),
      listTimelineConflicts(caseId),
    ]);
    setCaseItem(c);
    setDocuments(d);
    setCollaborators(co);
    setAudit(a);
    setStatements(st);
    setConflicts(cf);
  }, [caseId]);
  useEffect(() => {
    reload()
      .catch((e) => setToast({ type: "error", message: e.message }))
      .finally(() => setLoading(false));
  }, [reload]);
  useRefreshOnFocus(reload);
  if (loading) return <LoadingState label="Loading case…" />;
  if (!caseItem)
    return (
      <div className="center-message">
        <h2>Case unavailable</h2>
      </div>
    );
  const canManage =
    profile?.role === "ADMIN" ||
    (profile?.role === "INVESTIGATING_OFFICER" &&
      collaborators.some((c) => c.user_id === profile.id));
  return (
    <div>
      <header className="repo-header">
        <div className="repo-title">
          <BriefcaseBusiness size={22} />
          <div>
            <div className="repo-path">
              <span>{caseItem.case_number}</span>
              <span>/</span>
              <strong>{caseItem.title}</strong>
            </div>
            <p>{caseItem.description || "No description provided."}</p>
          </div>
          <span className="visibility-pill">Private</span>
        </div>
        <RepoTabs
          caseId={caseId}
          counts={{
            documents: documents.length,
            collaborators: collaborators.length,
            timeline: statements.length,
            audit: audit.length,
          }}
        />
      </header>
      <div className="page case-content">
        <Routes>
          <Route
            index
            element={
              <Overview
                c={caseItem}
                documents={documents}
                collaborators={collaborators}
                audit={audit}
              />
            }
          />
          <Route
            path="documents"
            element={
              <DocumentsTab
                caseId={caseId}
                documents={documents}
                reload={reload}
                setToast={setToast}
              />
            }
          />
          <Route
            path="collaborators"
            element={
              <CollaboratorsTab
                caseId={caseId}
                documents={documents}
                collaborators={collaborators}
                canManage={canManage}
                reload={reload}
                setToast={setToast}
              />
            }
          />
          <Route
            path="timeline"
            element={
              <ConflictsTab
                caseId={caseId}
                statements={statements}
                conflicts={conflicts}
                reload={reload}
                setToast={setToast}
              />
            }
          />
          <Route path="audit" element={<AuditTab audit={audit} />} />
        </Routes>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
function Overview({ c, documents, collaborators, audit }) {
  return (
    <div className="two-column">
      <section className="panel">
        <div className="panel-header readme-header">
          <h2>Case overview</h2>
          <span className="muted small">README-style summary</span>
        </div>
        <div className="readme-body">
          <h1>{c.title}</h1>
          <p>
            {c.description ||
              "No detailed case narrative has been written yet."}
          </p>
          <hr />
          <h3>Case number</h3>
          <code>{c.case_number}</code>
          <h3>Created</h3>
          <p>{formatDate(c.created_at)}</p>
        </div>
      </section>
      <aside className="stack">
        <section className="panel compact-panel">
          <h3>About</h3>
          <div className="about-row">
            <LockKeyhole size={16} />
            Private case workspace
          </div>
          <div className="about-row">
            <FileText size={16} />
            {documents.length} documents
          </div>
          <div className="about-row">
            <Users size={16} />
            {collaborators.length} collaborators
          </div>
          <div className="about-row">
            <History size={16} />
            {audit.length} audit events
          </div>
        </section>
        <section className="panel compact-panel">
          <h3>Collaborators</h3>
          <div className="avatar-row">
            {collaborators.slice(0, 8).map((x) => (
              <Avatar key={x.user_id} name={x.username} />
            ))}
          </div>
        </section>
      </aside>
    </div>
  );
}
const SINGLETON_TYPE_ALIASES = {
  FIR: "FIR",
  FIRSTINFORMATIONREPORT: "FIR",
  CHARGESHEET: "CHARGESHEET",
};
function singletonTypeKey(documentType) {
  if (!documentType) return null;
  const normalized = documentType.replace(/[^A-Za-z]/g, "").toUpperCase();
  return SINGLETON_TYPE_ALIASES[normalized] || null;
}
function DocumentsTab({ caseId, documents, reload, setToast }) {
  const [open, setOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [updateExisting, setUpdateExisting] = useState(false),
    [form, setForm] = useState({
      title: "",
      documentType: "",
      clearanceLevel: "RESTRICTED",
      file: null,
    });
  const nav = useNavigate();
  const singletonKey = singletonTypeKey(form.documentType);
  const matchingExisting = useMemo(
    () =>
      singletonKey
        ? documents.find(
            (d) => singletonTypeKey(d.document_type) === singletonKey,
          ) || null
        : null,
    [singletonKey, documents],
  );
  useEffect(() => {
    if (!matchingExisting) setUpdateExisting(false);
  }, [matchingExisting]);
  async function submit(e) {
    e.preventDefault();
    if (!form.file) return;
    if (matchingExisting && !updateExisting) {
      setToast({
        type: "error",
        message: `This case already has a primary ${singletonKey} ("${matchingExisting.title}"). Check the box to add this as a new version, or change the document type if this is genuinely different evidence.`,
      });
      return;
    }
    setBusy(true);
    try {
      if (matchingExisting && updateExisting) {
        await uploadDocumentVersion({
          document: matchingExisting,
          file: form.file,
          changeSummary: form.title || "Updated evidence",
        });
        setOpen(false);
        setForm({
          title: "",
          documentType: "",
          clearanceLevel: "RESTRICTED",
          file: null,
        });
        setUpdateExisting(false);
        await reload();
        setToast({
          message: `New version of "${matchingExisting.title}" registered - previous version stays available in its history.`,
        });
        nav(`/documents/${matchingExisting.id}`);
      } else {
        const r = await uploadNewDocument({ caseId, ...form });
        setOpen(false);
        setForm({
          title: "",
          documentType: "",
          clearanceLevel: "RESTRICTED",
          file: null,
        });
        await reload();
        setToast({ message: "Evidence uploaded as immutable version 1." });
        nav(`/documents/${r.documentId}`);
      }
    } catch (err) {
      if (err.code === "CONFLICT" && err.details?.existing_document_id) {
        setToast({
          type: "error",
          message: `${err.message} Check the "add as new version" box above and try again.`,
        });
      } else {
        setToast({ type: "error", message: err.message });
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Documents</h2>
          <p>
            Every update creates a new immutable version. Only one primary FIR
            and one primary chargesheet per case - further uploads of either
            become new versions.
          </p>
        </div>
        <button className="button button-primary" onClick={() => setOpen(true)}>
          <FilePlus2 size={16} /> Upload evidence
        </button>
      </div>
      {documents.length ? (
        <div className="data-list">
          <div className="data-header">
            <span>Name</span>
            <span>Clearance</span>
            <span>Version</span>
            <span>Created</span>
          </div>
          {documents.map((doc) => (
            <Link className="data-row" to={`/documents/${doc.id}`} key={doc.id}>
              <span className="doc-name">
                <FileText size={17} />
                <span>
                  <strong>{doc.title}</strong>
                  <small>{doc.document_type || "Unclassified type"}</small>
                </span>
              </span>
              <Badge tone={clearanceTone(doc.clearance_level)}>
                {doc.clearance_level}
              </Badge>
              <span>v{doc.current_version_number}</span>
              <span className="small muted">{formatDate(doc.created_at)}</span>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<FileText size={28} />}
          title="No evidence yet"
          description="Upload a PDF or supported image to create version 1."
        />
      )}
      {open ? (
        <Modal
          title="Upload evidence"
          onClose={() => setOpen(false)}
          footer={
            <>
              <button className="button" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button
                form="upload-doc"
                className="button button-primary"
                disabled={busy || (matchingExisting && !updateExisting)}
              >
                {busy
                  ? "Hashing & uploading…"
                  : matchingExisting && updateExisting
                    ? "Add as new version"
                    : "Upload evidence"}
              </button>
            </>
          }
        >
          <form id="upload-doc" className="form-stack" onSubmit={submit}>
            <label className="field">
              <span>Document title</span>
              <input
                required
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </label>
            <label className="field">
              <span>Document type</span>
              <input
                value={form.documentType}
                onChange={(e) =>
                  setForm({ ...form, documentType: e.target.value })
                }
                placeholder="FIR, charge sheet, statement…"
              />
            </label>
            {matchingExisting ? (
              <div
                style={{
                  background: "#fffbeb",
                  border: "1px solid #fde68a",
                  borderRadius: "8px",
                  padding: "0.75rem",
                  fontSize: "0.85rem",
                }}
              >
                <label
                  style={{
                    display: "flex",
                    gap: "0.5rem",
                    alignItems: "flex-start",
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={updateExisting}
                    onChange={(e) => setUpdateExisting(e.target.checked)}
                    style={{ marginTop: "0.2rem" }}
                  />
                  <span>
                    This case already has a primary {singletonKey} -{" "}
                    <strong>"{matchingExisting.title}"</strong> (v
                    {matchingExisting.current_version_number}). Check this to
                    add your file as a new version of it. The previous version
                    stays stored and viewable in its version history - nothing
                    is deleted.
                  </span>
                </label>
              </div>
            ) : null}
            <label className="field">
              <span>Clearance</span>
              <select
                value={form.clearanceLevel}
                onChange={(e) =>
                  setForm({ ...form, clearanceLevel: e.target.value })
                }
              >
                {["PUBLIC", "RESTRICTED", "CONFIDENTIAL", "SECRET"].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>File · max 25 MB</span>
              <input
                required
                type="file"
                accept="application/pdf,image/jpeg,image/png,image/tiff"
                onChange={(e) =>
                  setForm({ ...form, file: e.target.files?.[0] || null })
                }
              />
            </label>
          </form>
        </Modal>
      ) : null}
    </section>
  );
}
const CLEARANCE_RANK = { PUBLIC: 1, RESTRICTED: 2, CONFIDENTIAL: 3, SECRET: 4 };
function CollaboratorsTab({
  caseId,
  documents,
  collaborators,
  canManage,
  reload,
  setToast,
}) {
  const [open, setOpen] = useState(false),
    [candidates, setCandidates] = useState([]),
    [selected, setSelected] = useState(""),
    [busy, setBusy] = useState(false);
  const assigned = useMemo(
    () => new Set(collaborators.map((c) => c.user_id)),
    [collaborators],
  );
  const maxDocClearance = useMemo(
    () =>
      documents.reduce(
        (max, d) => Math.max(max, CLEARANCE_RANK[d.clearance_level] || 1),
        1,
      ),
    [documents],
  );
  const selectedCandidate = candidates.find((c) => c.id === selected);
  const clearanceWarning =
    selectedCandidate &&
    CLEARANCE_RANK[selectedCandidate.clearance_level] < maxDocClearance;
  async function picker() {
    try {
      setCandidates(
        (await listCollaboratorCandidates(caseId)).filter(
          (c) => !assigned.has(c.id),
        ),
      );
      setOpen(true);
    } catch (e) {
      setToast({ type: "error", message: e.message });
    }
  }
  async function add() {
    if (!selected) return;
    setBusy(true);
    try {
      await addCollaborator(caseId, selected);
      await reload();
      setOpen(false);
      setSelected("");
      setToast({ message: "Collaborator added." });
    } catch (e) {
      setToast({ type: "error", message: e.message });
    } finally {
      setBusy(false);
    }
  }
  async function remove(id) {
    if (!confirm("Remove this collaborator?")) return;
    try {
      await removeCollaborator(caseId, id);
      await reload();
      setToast({ message: "Collaborator removed." });
    } catch (e) {
      setToast({ type: "error", message: e.message });
    }
  }
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Manage access</h2>
          <p>
            Only admins or assigned investigating officers can change
            membership.
          </p>
        </div>
        {canManage ? (
          <button className="button button-primary" onClick={picker}>
            <UserPlus size={16} /> Add collaborator
          </button>
        ) : null}
      </div>
      <div className="collaborator-list">
        {collaborators.map((x) => (
          <div className="collaborator-row" key={x.user_id}>
            <Avatar name={x.username} />
            <div className="collab-main">
              <strong>{x.username}</strong>
              <span>
                {x.role.replaceAll("_", " ")} · {x.clearance_level}
              </span>
            </div>
            <span className="muted small">
              Added by {x.assigned_by_username}
              <br />
              {formatDate(x.assigned_at)}
            </span>
            {canManage ? (
              <button
                className="icon-button danger-icon"
                onClick={() => remove(x.user_id)}
              >
                <Trash2 size={17} />
              </button>
            ) : null}
          </div>
        ))}
      </div>
      {open ? (
        <Modal
          title="Add a collaborator"
          onClose={() => setOpen(false)}
          footer={
            <>
              <button className="button" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button
                className="button button-primary"
                disabled={!selected || busy}
                onClick={add}
              >
                {busy ? "Adding…" : "Add collaborator"}
              </button>
            </>
          }
        >
          <label className="field">
            <span>Active user</span>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              <option value="">Select user…</option>
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.username} — {c.role} / {c.clearance_level}
                </option>
              ))}
            </select>
          </label>
          {clearanceWarning ? (
            <p
              style={{
                color: "#b45309",
                fontSize: "0.85rem",
                marginTop: "0.5rem",
              }}
            >
              ⚠ {selectedCandidate.username}'s clearance (
              {selectedCandidate.clearance_level}) is below this case's
              highest-clearance evidence. They'll be able to open the case but
              won't see all documents until an admin raises their clearance.
            </p>
          ) : null}
        </Modal>
      ) : null}
    </section>
  );
}
function ConflictsTab({ caseId, statements, conflicts, reload, setToast }) {
  const [open, setOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [generating, setGenerating] = useState(false),
    [actingOn, setActingOn] = useState(null),
    [form, setForm] = useState({
      personName: "",
      locationName: "",
      windowStart: "",
      windowEnd: "",
      durationMinutes: 30,
      sourceExcerpt: "",
    });
  const openConflicts = conflicts.filter((c) => c.status === "OPEN");
  const suggested = statements.filter((s) => s.status === "SUGGESTED");
  const confirmed = statements.filter((s) => s.status === "CONFIRMED");
  const byId = useMemo(
    () => Object.fromEntries(statements.map((s) => [s.id, s])),
    [statements],
  );
  async function generate() {
    setGenerating(true);
    try {
      const created = await generateTimelineSuggestions(caseId);
      await reload();
      setToast({
        message: created.length
          ? `${created.length} candidate statement(s) found from uploaded documents - review below.`
          : "No new candidates found. Confirm entities on your documents first, or add a statement manually.",
      });
    } catch (e) {
      setToast({ type: "error", message: e.message });
    } finally {
      setGenerating(false);
    }
  }
  async function accept(id) {
    setActingOn(id);
    try {
      const r = await confirmTimelineSuggestion(caseId, id);
      await reload();
      setToast(
        r.contradiction_detected
          ? {
              type: "error",
              message:
                "Confirmed - this creates a contradiction, see Open conflicts below.",
            }
          : { message: "Statement confirmed." },
      );
    } catch (e) {
      setToast({ type: "error", message: e.message });
    } finally {
      setActingOn(null);
    }
  }
  async function reject(id) {
    setActingOn(id);
    try {
      await rejectTimelineSuggestion(caseId, id);
      await reload();
      setToast({ message: "Suggestion dismissed." });
    } catch (e) {
      setToast({ type: "error", message: e.message });
    } finally {
      setActingOn(null);
    }
  }
  async function submit(e) {
    e.preventDefault();
    if (
      !form.personName ||
      !form.locationName ||
      !form.windowStart ||
      !form.windowEnd
    )
      return;
    setBusy(true);
    try {
      const r = await addTimelineStatement(caseId, {
        person_name: form.personName,
        location_name: form.locationName,
        window_start: new Date(form.windowStart).toISOString(),
        window_end: new Date(form.windowEnd).toISOString(),
        duration_minutes: Number(form.durationMinutes) || 30,
        source_excerpt: form.sourceExcerpt || null,
      });
      setOpen(false);
      setForm({
        personName: "",
        locationName: "",
        windowStart: "",
        windowEnd: "",
        durationMinutes: 30,
        sourceExcerpt: "",
      });
      await reload();
      setToast(
        r.contradiction_detected
          ? {
              type: "error",
              message: `Contradiction detected for ${form.personName} - see Open conflicts below.`,
            }
          : { message: "Statement added." },
      );
    } catch (err) {
      setToast({ type: "error", message: err.message });
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Conflicts</h2>
          <p>
            Finds people who can't have been where evidence says, at the same
            time, given travel time between locations.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button className="button" onClick={generate} disabled={generating}>
            {generating
              ? "Scanning documents…"
              : "Scan documents for candidates"}
          </button>
          <button
            className="button button-primary"
            onClick={() => setOpen(true)}
          >
            <UserPlus size={16} /> Add manually
          </button>
        </div>
      </div>

      {openConflicts.length ? (
        <div className="data-list" style={{ marginBottom: "1.25rem" }}>
          {openConflicts.map((c) => (
            <div
              key={c.id}
              className="data-row"
              style={{ alignItems: "flex-start", gridTemplateColumns: "1fr" }}
            >
              <div>
                <Badge tone="danger">Contradiction</Badge>
                <strong style={{ marginLeft: "0.5rem" }}>
                  {c.person_name}
                </strong>
                <p className="small muted" style={{ margin: "0.35rem 0 0" }}>
                  No valid schedule reconciles these statements, even letting
                  each stated window shift freely, given known travel time
                  between the locations involved:
                </p>
                <ul style={{ margin: "0.35rem 0 0", paddingLeft: "1.1rem" }}>
                  {c.statement_ids.map((id) =>
                    byId[id] ? (
                      <li key={id} className="small">
                        <strong>{byId[id].location_name}</strong> ·{" "}
                        {formatDate(byId[id].window_start)} –{" "}
                        {formatDate(byId[id].window_end)}
                        {byId[id].source_excerpt ? (
                          <>
                            <br />
                            <span className="muted">
                              {byId[id].source_excerpt}
                            </span>
                          </>
                        ) : null}
                      </li>
                    ) : null,
                  )}
                </ul>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<History size={28} />}
          title="No contradictions found yet"
          description="Scan documents for candidates, add a statement manually, or both - conflicts appear here automatically once two statements about the same person can't both be true."
        />
      )}

      {suggested.length ? (
        <>
          <h3 style={{ margin: "1.5rem 0 0.5rem", fontSize: "0.95rem" }}>
            Candidates from documents - review before they count as evidence
          </h3>
          <div className="data-list">
            {suggested.map((s) => (
              <div
                className="data-row"
                key={s.id}
                style={{
                  alignItems: "flex-start",
                  gridTemplateColumns: "1fr auto",
                }}
              >
                <div>
                  <strong>{s.person_name}</strong> · {s.location_name}{" "}
                  <span className="muted small">
                    ({formatDate(s.window_start)} – {formatDate(s.window_end)})
                  </span>
                  <p className="small muted" style={{ margin: "0.25rem 0 0" }}>
                    {s.source_excerpt}
                  </p>
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: "0.4rem",
                    alignItems: "center",
                  }}
                >
                  <button
                    className="button"
                    disabled={actingOn === s.id}
                    onClick={() => reject(s.id)}
                  >
                    Dismiss
                  </button>
                  <button
                    className="button button-primary"
                    disabled={actingOn === s.id}
                    onClick={() => accept(s.id)}
                  >
                    {actingOn === s.id ? "Confirming…" : "Confirm"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : null}

      {confirmed.length ? (
        <>
          <h3 style={{ margin: "1.5rem 0 0.5rem", fontSize: "0.95rem" }}>
            Confirmed statements
          </h3>
          <div className="data-list">
            <div className="data-header">
              <span>Person</span>
              <span>Location</span>
              <span>Window</span>
              <span>Source</span>
            </div>
            {confirmed.map((s) => (
              <div className="data-row" key={s.id}>
                <span>
                  <strong>{s.person_name}</strong>
                </span>
                <span>{s.location_name}</span>
                <span className="small muted">
                  {formatDate(s.window_start)} – {formatDate(s.window_end)}
                </span>
                <span className="small muted">{s.source_excerpt || "—"}</span>
              </div>
            ))}
          </div>
        </>
      ) : null}

      {open ? (
        <Modal
          title="Add statement manually"
          onClose={() => setOpen(false)}
          footer={
            <>
              <button className="button" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button
                form="add-statement"
                className="button button-primary"
                disabled={busy}
              >
                {busy ? "Checking…" : "Add & check"}
              </button>
            </>
          }
        >
          <form id="add-statement" className="form-stack" onSubmit={submit}>
            <label className="field">
              <span>Person</span>
              <input
                required
                value={form.personName}
                onChange={(e) =>
                  setForm({ ...form, personName: e.target.value })
                }
                placeholder="Rakesh Sharma"
              />
            </label>
            <label className="field">
              <span>Location</span>
              <input
                required
                value={form.locationName}
                onChange={(e) =>
                  setForm({ ...form, locationName: e.target.value })
                }
                placeholder="City / place name, exact spelling matters"
              />
            </label>
            <label className="field">
              <span>Window start</span>
              <input
                required
                type="datetime-local"
                value={form.windowStart}
                onChange={(e) =>
                  setForm({ ...form, windowStart: e.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Window end</span>
              <input
                required
                type="datetime-local"
                value={form.windowEnd}
                onChange={(e) =>
                  setForm({ ...form, windowEnd: e.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Expected duration (minutes)</span>
              <input
                type="number"
                min="1"
                value={form.durationMinutes}
                onChange={(e) =>
                  setForm({ ...form, durationMinutes: e.target.value })
                }
              />
            </label>
            <label className="field">
              <span>Source excerpt (optional)</span>
              <input
                value={form.sourceExcerpt}
                onChange={(e) =>
                  setForm({ ...form, sourceExcerpt: e.target.value })
                }
                placeholder="Quote or reference from the statement"
              />
            </label>
          </form>
        </Modal>
      ) : null}
    </section>
  );
}
function AuditTab({ audit }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Audit trail</h2>
          <p>Append-only globally hash-chained case events.</p>
        </div>
      </div>
      <div className="audit-table">
        <div className="audit-head">
          <span>#</span>
          <span>Event</span>
          <span>Actor</span>
          <span>Result</span>
          <span>Hash</span>
          <span>Time</span>
        </div>
        {audit.map((e) => (
          <div className="audit-row" key={e.sequence}>
            <code>{e.sequence}</code>
            <span>
              <strong>{e.action.replaceAll("_", " ")}</strong>
              {e.reason ? <small>{e.reason}</small> : null}
            </span>
            <span>{e.actor_username || "system"}</span>
            <Badge
              tone={
                e.result === "SUCCESS"
                  ? "success"
                  : e.result === "DENIED"
                    ? "danger"
                    : "warning"
              }
            >
              {e.result}
            </Badge>
            <code title={e.entry_hash}>{shortHash(e.entry_hash)}</code>
            <span className="small muted">{formatDate(e.timestamp)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
