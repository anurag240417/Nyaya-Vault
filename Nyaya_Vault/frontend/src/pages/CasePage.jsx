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
export default function CasePage() {
  const { caseId } = useParams();
  const { profile } = useAuth();
  const [caseItem, setCaseItem] = useState(null),
    [documents, setDocuments] = useState([]),
    [collaborators, setCollaborators] = useState([]),
    [audit, setAudit] = useState([]),
    [loading, setLoading] = useState(true),
    [toast, setToast] = useState(null);
  const reload = useCallback(async () => {
    const [c, d, co, a] = await Promise.all([
      getCase(caseId),
      listCaseDocuments(caseId),
      getCaseCollaborators(caseId),
      getCaseAudit(caseId),
    ]);
    setCaseItem(c);
    setDocuments(d);
    setCollaborators(co);
    setAudit(a);
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
                collaborators={collaborators}
                canManage={canManage}
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
function DocumentsTab({ caseId, documents, reload, setToast }) {
  const [open, setOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [form, setForm] = useState({
      title: "",
      documentType: "",
      clearanceLevel: "RESTRICTED",
      file: null,
    });
  const nav = useNavigate();
  async function submit(e) {
    e.preventDefault();
    if (!form.file) return;
    setBusy(true);
    try {
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
          <h2>Documents</h2>
          <p>Every update creates a new immutable version.</p>
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
                disabled={busy}
              >
                {busy ? "Hashing & uploading…" : "Upload evidence"}
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
function CollaboratorsTab({
  caseId,
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
