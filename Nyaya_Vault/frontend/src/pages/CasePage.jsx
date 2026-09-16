import { useCallback, useEffect, useMemo, useState } from "react";
import { Route, Routes, useNavigate, useParams, Link } from "react-router-dom";
import {
  BriefcaseBusiness,
  FileOutput,
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
  uploadDocumentVersion,
  updateCase,
} from "../lib/api";
import { formatDate, shortHash } from "../lib/format";
import { useAuth } from "../context/AuthContext";
import DossierTabs from "../components/DossierTabs";
import Badge, {
  clearanceTone,
  departmentTone,
  statusTone,
} from "../components/Badge";
import Avatar from "../components/Avatar";
import Modal from "../components/Modal";
import NoticeModal from "../components/NoticeModal";
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
import {
  askCaseAssistant,
  getCaseSummary,
  getLegalSectionSuggestions,
  getCaseGaps,
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
      <header className="dossier-header">
        <div className="dossier-title">
          <BriefcaseBusiness size={22} />
          <div>
            <div className="dossier-identity">
              <span className="case-reference">Case dossier · {caseItem.case_number}</span>
              <h1>{caseItem.title}</h1>
            </div>
            <p>{caseItem.description || "No description provided."}</p>
          </div>
          <span className="visibility-pill">Private</span>
          <Badge tone={statusTone(caseItem.status)}>
            {(caseItem.status || "UNDER_INVESTIGATION").replaceAll("_", " ")}
          </Badge>
        </div>
        <DossierTabs
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
                caseId={caseId}
                c={caseItem}
                documents={documents}
                collaborators={collaborators}
                audit={audit}
                canManage={canManage}
                reload={reload}
                setToast={setToast}
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
          <Route path="assistant" element={<AssistantTab caseId={caseId} />} />
          <Route path="audit" element={<AuditTab audit={audit} />} />
        </Routes>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
function Overview({
  caseId,
  c,
  documents,
  collaborators,
  audit,
  canManage,
  reload,
  setToast,
}) {
  const [noticeModal, setNoticeModal] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  async function changeStatus(newStatus) {
    if (newStatus === c.status) return;
    setStatusBusy(true);
    try {
      await updateCase(caseId, { status: newStatus });
      await reload();
      setToast({
        message: `Case status updated to ${newStatus.replaceAll("_", " ")}.`,
      });
    } catch (err) {
      setToast({ type: "error", message: err.message });
    } finally {
      setStatusBusy(false);
    }
  }
  return (
    <div className="two-column">
      <section className="panel">
        <div className="panel-header summary-header">
          <h2>Official Case Summary</h2>
          <span className="muted small">Case record</span>
        </div>
        <div className="record-body">
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
          <h3>Case Control</h3>
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
          {canManage ? (
            <label className="field section-spacer">
              <span>Case status</span>
              <select
                value={c.status || "UNDER_INVESTIGATION"}
                disabled={statusBusy}
                onChange={(e) => changeStatus(e.target.value)}
              >
                {["UNDER_INVESTIGATION", "SOLVED", "UNSOLVED", "CLOSED"].map(
                  (s) => (
                    <option key={s} value={s}>
                      {s.replaceAll("_", " ")}
                    </option>
                  ),
                )}
              </select>
            </label>
          ) : null}
          <button
            className="button button-official button-block section-spacer"
            onClick={() => setNoticeModal(true)}
          >
            <FileOutput size={16} /> Generate legal notice
          </button>
        </section>
        <section className="panel compact-panel">
          <h3>Assigned Personnel</h3>
          <div className="avatar-row">
            {collaborators.slice(0, 8).map((x) => (
              <Avatar key={x.user_id} name={x.username} />
            ))}
          </div>
        </section>
      </aside>
      {noticeModal ? (
        <NoticeModal
          caseId={caseId}
          onClose={() => setNoticeModal(false)}
          setToast={setToast}
        />
      ) : null}
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
      department: "GENERAL",
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
          department: "GENERAL",
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
          department: "GENERAL",
          file: null,
        });
        await reload();
        setToast({ message: "Evidence uploaded as immutable version 1." });
        nav(`/documents/${r.documentId}`);
      }
    } catch (err) {
      if (
        err.code === "CONFLICT" &&
        err.details?.reason === "SINGLETON_DOCUMENT_TYPE_EXISTS"
      ) {
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
          <h2>Evidence Register</h2>
          <p>
            Every update creates a new immutable version. Only one primary FIR
            and one primary chargesheet per case - further uploads of either
            become new versions.
          </p>
        </div>
        <button className="button button-primary" onClick={() => setOpen(true)}>
          <FilePlus2 size={16} /> Register evidence
        </button>
      </div>
      {documents.length ? (
        <div className="data-list" tabIndex={0} aria-label="Evidence register, scroll for all columns">
          <div className="data-header">
            <span>Evidence / type</span>
            <span>Classification</span>
            <span>Department</span>
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
                  <code className="evidence-id">{doc.id}</code>
                </span>
              </span>
              <Badge tone={clearanceTone(doc.clearance_level)}>
                {doc.clearance_level}
              </Badge>
              <Badge tone={departmentTone(doc.department)}>
                {doc.department || "GENERAL"}
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
          title="Register evidence"
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
                    : "Register evidence"}
              </button>
            </>
          }
        >
          <form id="upload-doc" className="form-stack" onSubmit={submit}>
            <label className="field">
              <span>01 · Evidence title</span>
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
              <div className="version-warning">
                <label>
                  <input
                    type="checkbox"
                    checked={updateExisting}
                    onChange={(e) => setUpdateExisting(e.target.checked)}
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
              <span>02 · Security classification</span>
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
              <span>03 · Responsible department</span>
              <select
                value={form.department}
                onChange={(e) =>
                  setForm({ ...form, department: e.target.value })
                }
              >
                {[
                  "GENERAL",
                  "POLICE",
                  "FORENSICS",
                  "PROSECUTION",
                  "JUDICIARY",
                ].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>04 · File selection · max 200 MB</span>
              <input
                required
                type="file"
                accept="application/pdf,image/jpeg,image/png,image/tiff,video/mp4,video/quicktime,video/webm"
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
          <h2>Case Access & Assigned Personnel</h2>
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
                className="icon-button danger-icon" aria-label={`Remove access for ${x.username}`}
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
            <p className="warning-note section-spacer">
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
          <h2>Evidence Timeline & Contradiction Review</h2>
          <p>
            Finds people who can't have been where evidence says, at the same
            time, given travel time between locations.
          </p>
        </div>
        <div className="button-row">
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
        <div className="contradiction-list">
          {openConflicts.map((c) => (
            <div
              key={c.id}
              className="contradiction-sheet"
            >
              <div>
                <Badge tone="danger">Contradiction</Badge>
                <strong className="contradiction-person">
                  {c.person_name}
                </strong>
                <p className="small muted compact-copy">
                  No valid schedule reconciles these statements, even letting
                  each stated window shift freely, given known travel time
                  between the locations involved:
                </p>
                <ul className="statement-comparison">
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
          <h3 className="review-heading">
            System extracted — requires human confirmation
          </h3>
          <div className="data-list">
            {suggested.map((s) => (
              <div
                className="data-row suggestion-row"
                key={s.id}
              >
                <div>
                  <strong>{s.person_name}</strong> · {s.location_name}{" "}
                  <span className="muted small">
                    ({formatDate(s.window_start)} – {formatDate(s.window_end)})
                  </span>
                  <p className="small muted compact-copy">
                    {s.source_excerpt}
                  </p>
                </div>
                <div className="button-row">
                  <button
                    className="button button-quiet"
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
          <h3 className="review-heading">
            Confirmed statements
          </h3>
          <div className="data-list confirmed-register">
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
function AssistantTab({ caseId }) {
  const [gaps, setGaps] = useState(null),
    [gapsError, setGapsError] = useState(null);
  const [messages, setMessages] = useState([]),
    [question, setQuestion] = useState(""),
    [asking, setAsking] = useState(false);
  const [summary, setSummary] = useState(null),
    [summarizing, setSummarizing] = useState(false);
  const [legal, setLegal] = useState(null),
    [suggestingLegal, setSuggestingLegal] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    getCaseGaps(caseId)
      .then(setGaps)
      .catch((e) => setGapsError(e.message));
  }, [caseId]);
  function severityTone(s) {
    return s === "HIGH" ? "danger" : s === "MEDIUM" ? "warning" : "info";
  }
  async function ask(e) {
    e.preventDefault();
    if (!question.trim() || asking) return;
    const q = question.trim();
    setQuestion("");
    setError(null);
    setMessages((m) => [...m, { role: "user", text: q }]);
    setAsking(true);
    try {
      const r = await askCaseAssistant(caseId, q);
      setMessages((m) => [...m, { role: "assistant", text: r.answer }]);
    } catch (err) {
      setError(err.message);
      setMessages((m) => m.slice(0, -1));
      setQuestion(q);
    } finally {
      setAsking(false);
    }
  }
  async function generateSummary() {
    setSummarizing(true);
    setError(null);
    try {
      const r = await getCaseSummary(caseId);
      setSummary(r.summary);
    } catch (err) {
      setError(err.message);
    } finally {
      setSummarizing(false);
    }
  }
  async function generateLegal() {
    setSuggestingLegal(true);
    setError(null);
    try {
      const r = await getLegalSectionSuggestions(caseId);
      setLegal(r.suggestion);
    } catch (err) {
      setError(err.message);
    } finally {
      setSuggestingLegal(false);
    }
  }
  return (
    <div className="two-column">
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Case Research Assistant</h2>
            <p>
              Answers are grounded only in this case's own confirmed evidence
              and cite their source. Not a legal or factual authority - verify
              anything important yourself.
            </p>
          </div>
        </div>
        <div className="research-records">
          {messages.length === 0 ? (
            <p className="muted small">
              No questions asked yet this session. Try: "Who has been placed at
              more than one location?" or "What evidence do we have so far?"
            </p>
          ) : null}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`research-entry ${m.role === "user" ? "research-query" : "research-answer"}`}
            >
              <span className="eyebrow">{m.role === "user" ? "Research query" : "Generated answer · verify against sources"}</span>
              {m.text}
            </div>
          ))}
          {asking ? <div className="muted small">Thinking…</div> : null}
        </div>
        <form onSubmit={ask} className="research-form">
          <div className="field grow">
            <input
              aria-label="Research question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question about this case…"
              disabled={asking}
            />
          </div>
          <button
            className="button button-primary"
            disabled={asking || !question.trim()}
          >
            Ask
          </button>
        </form>
        {error ? (
          <p className="form-error section-spacer">
            {error}
          </p>
        ) : null}
      </section>
      <aside className="stack">
        <section className="panel compact-panel">
          <h3>Case gap check</h3>
          <p className="muted small">
            Computed directly from case data - not AI-generated, always exact.
          </p>
          {gapsError ? (
            <p className="form-error">{gapsError}</p>
          ) : gaps === null ? (
            <LoadingState label="Checking…" />
          ) : gaps.length === 0 ? (
            <p className="muted small">No gaps found.</p>
          ) : (
            <div className="gap-list">
              {gaps.map((g, i) => (
                <div
                  key={i}
                 className="gap-row">
                  <Badge tone={severityTone(g.severity)}>{g.severity}</Badge>
                  <span className="small">{g.message}</span>
                </div>
              ))}
            </div>
          )}
        </section>
        <section className="panel compact-panel">
          <h3>Investigative briefing</h3>
          <button
            className="button button-block"
            disabled={summarizing}
            onClick={generateSummary}
          >
            {summarizing ? "Generating…" : "Generate summary"}
          </button>
          {summary ? (
            <div
              className="small research-output"
            >
              {summary}
            </div>
          ) : null}
        </section>
        <section className="panel compact-panel">
          <h3>Possible legal sections</h3>
          <p className="muted small warning-note">
            ⚠ Preliminary and non-authoritative. A qualified legal officer must
            independently verify before relying on this.
          </p>
          <button
            className="button button-block"
            disabled={suggestingLegal}
            onClick={generateLegal}
          >
            {suggestingLegal ? "Analyzing…" : "Suggest sections to review"}
          </button>
          {legal ? (
            <div
              className="small research-output"
            >
              {legal}
            </div>
          ) : null}
        </section>
      </aside>
    </div>
  );
}
function AuditTab({ audit }) {
  const [actorDept, setActorDept] = useState("ALL"),
    [docDept, setDocDept] = useState("ALL");
  const deptOptions = (key) => [
    "ALL",
    ...new Set(audit.map((e) => e[key]).filter(Boolean)),
  ];
  const filtered = audit.filter(
    (e) =>
      (actorDept === "ALL" || e.actor_department === actorDept) &&
      (docDept === "ALL" || e.document_department === docDept),
  );
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Immutable Audit Ledger</h2>
          <p>Append-only globally hash-chained case events.</p>
        </div>
        <div className="button-row">
          <label className="field">
            <span className="small muted">Actor dept.</span>
            <select
              value={actorDept}
              onChange={(e) => setActorDept(e.target.value)}
            >
              {deptOptions("actor_department").map((d) => (
                <option key={d} value={d}>
                  {d === "ALL" ? "All" : d}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="small muted">Evidence dept.</span>
            <select
              value={docDept}
              onChange={(e) => setDocDept(e.target.value)}
            >
              {deptOptions("document_department").map((d) => (
                <option key={d} value={d}>
                  {d === "ALL" ? "All" : d}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      {(actorDept !== "ALL" || docDept !== "ALL") && filtered.length === 0 ? (
        <div className="panel-empty">
          No events match this department filter.
        </div>
      ) : null}
      <div className="audit-table" tabIndex={0} aria-label="Audit ledger, scroll for all columns">
        <div className="audit-head">
          <span>Sequence</span>
          <span>Event</span>
          <span>Actor</span>
          <span>Result</span>
          <span>Hash</span>
          <span>Time</span>
        </div>
        {filtered.map((e) => (
          <div className="audit-row" key={e.sequence}>
            <code>{e.sequence}</code>
            <span>
              <strong>{e.action.replaceAll("_", " ")}</strong>
              {e.reason ? <small>{e.reason}</small> : null}
              {e.document_department ? (
                <small>Evidence dept: {e.document_department}</small>
              ) : null}
            </span>
            <span>
              {e.actor_username || "system"}
              {e.actor_department ? <small>{e.actor_department}</small> : null}
            </span>
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
            <details className="hash-disclosure"><summary><code>{shortHash(e.entry_hash)}</code></summary><code className="wrap-code">{e.entry_hash}</code></details>
            <span className="small muted">{formatDate(e.timestamp)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
