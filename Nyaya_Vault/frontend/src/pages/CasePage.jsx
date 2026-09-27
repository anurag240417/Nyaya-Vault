import DocumentKindIcon from "../components/DocumentKindIcon";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
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
import AssistantResponse from "../components/AssistantResponse";
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
  const { t } = useTranslation("casePage");
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
  if (loading) return <LoadingState label={t("common.loadingCase")} />;
  if (!caseItem)
    return (
      <div className="center-message">
        <h2>{t("common.caseUnavailable")}</h2>
      </div>
    );
  const canManage =
    profile?.role === "ADMIN" ||
    (profile?.role === "INVESTIGATING_OFFICER" &&
      collaborators.some((c) => c.user_id === profile.id));
  // Mirrors backend require_remove_collaborator: only an admin or the lead IO
  // may remove access, and judges may only be removed by an admin.
  const leadId = caseItem.primary_investigator_id || caseItem.created_by;
  const canRemove = (c) =>
    profile?.role === "ADMIN" ||
    (profile?.role === "INVESTIGATING_OFFICER" &&
      profile.id === leadId &&
      c.role !== "JUDGE" &&
      c.user_id !== leadId);
  return (
    <div>
      <header className="dossier-header">
        <div className="dossier-title">
          <BriefcaseBusiness size={22} />
          <div>
            <div className="dossier-identity">
              <span className="case-reference">{t("common.caseDossier", { caseNumber: caseItem.case_number })}</span>
              <h1>{caseItem.title}</h1>
            </div>
            <p>{caseItem.description || t("common.noDescription")}</p>
          </div>
          <span className="visibility-pill" data-guide="visibility-pill">{t("common.private")}</span>
          <Badge tone={statusTone(caseItem.status)} data-guide="case-status">
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
                canRemove={canRemove}
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
  const { t } = useTranslation("casePage");
  const [noticeModal, setNoticeModal] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  async function changeStatus(newStatus) {
    if (newStatus === c.status) return;
    setStatusBusy(true);
    try {
      await updateCase(caseId, { status: newStatus });
      await reload();
      setToast({
        message: t("overview.statusUpdated", {
          status: newStatus.replaceAll("_", " "),
        }),
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
          <h2>{t("overview.summaryTitle")}</h2>
          <span className="muted small">{t("overview.caseRecord")}</span>
        </div>
        <div className="record-body">
          <h1>{c.title}</h1>
          <p>
            {c.description ||
              t("overview.noNarrative")}
          </p>
          <hr />
          <h3>{t("overview.caseNumber")}</h3>
          <code>{c.case_number}</code>
          <h3>{t("overview.created")}</h3>
          <p>{formatDate(c.created_at)}</p>
        </div>
      </section>
      <aside className="stack">
        <section className="panel compact-panel" data-guide="case-control">
          <h3>{t("overview.caseControl")}</h3>
          <div className="about-row">
            <LockKeyhole size={16} />
            {t("overview.privateWorkspace")}
          </div>
          <div className="about-row">
            <FileText size={16} />
            {t("overview.documentsCount", { count: documents.length })}
          </div>
          <div className="about-row">
            <Users size={16} />
            {t("overview.collaboratorsCount", { count: collaborators.length })}
          </div>
          <div className="about-row">
            <History size={16} />
            {t("overview.auditEventsCount", { count: audit.length })}
          </div>
          {canManage ? (
            <label className="field section-spacer" data-guide="case-status-select">
              <span>{t("overview.caseStatus")}</span>
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
            data-guide="legal-notice"
            onClick={() => setNoticeModal(true)}
          >
            <FileOutput size={16} /> {t("overview.generateLegalNotice")}
          </button>
        </section>
        <section className="panel compact-panel" data-guide="assigned-personnel">
          <h3>{t("overview.assignedPersonnel")}</h3>
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
  const { t } = useTranslation("casePage");
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
        message: t("documents.alreadyPrimaryError", {
          type: singletonKey,
          title: matchingExisting.title,
        }),
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
          message: t("documents.newVersionRegistered", {
            title: matchingExisting.title,
          }),
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
        setToast({ message: t("documents.uploadedAsVersion1") });
        nav(`/documents/${r.documentId}`);
      }
    } catch (err) {
      if (
        err.code === "CONFLICT" &&
        err.details?.reason === "SINGLETON_DOCUMENT_TYPE_EXISTS"
      ) {
        setToast({
          type: "error",
          message: t("documents.conflictRetry", { message: err.message }),
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
          <h2>{t("documents.title")}</h2>
          <p>
            {t("documents.description")}
          </p>
        </div>
        <button className="button button-primary" data-guide="register-evidence" onClick={() => setOpen(true)}>
          <FilePlus2 size={16} /> {t("documents.registerEvidence")}
        </button>
      </div>
      {documents.length ? (
        <div className="data-list" tabIndex={0} aria-label={t("documents.ariaScroll")}>
          <div className="data-header">
            <span>{t("documents.colEvidenceType")}</span>
            <span>{t("documents.colClassification")}</span>
            <span>{t("documents.colDepartment")}</span>
            <span>{t("documents.colVersion")}</span>
            <span>{t("documents.colCreated")}</span>
          </div>
          {documents.map((doc) => (
            <Link className="data-row" to={`/documents/${doc.id}`} key={doc.id} data-guide="evidence-row">
              <span className="doc-name">
                <DocumentKindIcon doc={doc} />
                <span>
                  <strong>{doc.title}</strong>
                  <small>{doc.document_type || t("documents.unclassifiedType")}</small>
                  <code className="evidence-id">{doc.id}</code>
                </span>
              </span>
              <Badge tone={clearanceTone(doc.clearance_level)} data-guide="clearance-badge">
                {doc.clearance_level}
              </Badge>
              <Badge tone={departmentTone(doc.department)} data-guide="department-badge">
                {doc.department || "GENERAL"}
              </Badge>
              <span data-guide="doc-version">v{doc.current_version_number}</span>
              <span className="small muted">{formatDate(doc.created_at)}</span>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<FileText size={28} />}
          title={t("documents.emptyTitle")}
          description={t("documents.emptyDescription")}
        />
      )}
      {open ? (
        <Modal
          title={t("documents.modalTitle")}
          onClose={() => setOpen(false)}
          footer={
            <>
              <button className="button" onClick={() => setOpen(false)}>
                {t("documents.cancel")}
              </button>
              <button
                form="upload-doc"
                className="button button-primary"
                disabled={busy || (matchingExisting && !updateExisting)}
              >
                {busy
                  ? t("documents.hashingUploading")
                  : matchingExisting && updateExisting
                    ? t("documents.addAsNewVersion")
                    : t("documents.registerEvidence")}
              </button>
            </>
          }
        >
          <form id="upload-doc" className="form-stack" onSubmit={submit}>
            <label className="field">
              <span>{t("documents.fieldTitle")}</span>
              <input
                required
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </label>
            <label className="field" data-guide="upload-doc-type">
              <span>{t("documents.fieldDocType")}</span>
              <input
                value={form.documentType}
                onChange={(e) =>
                  setForm({ ...form, documentType: e.target.value })
                }
                placeholder={t("documents.docTypePlaceholder")}
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
                    {t("documents.versionWarning", {
                      type: singletonKey,
                      title: matchingExisting.title,
                      version: matchingExisting.current_version_number,
                    })}
                  </span>
                </label>
              </div>
            ) : null}
            <label className="field" data-guide="upload-classification">
              <span>{t("documents.fieldClassification")}</span>
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
            <label className="field" data-guide="upload-department">
              <span>{t("documents.fieldDepartment")}</span>
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
            <label className="field" data-guide="upload-file">
              <span>{t("documents.fieldFile")}</span>
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
  canRemove,
  reload,
  setToast,
}) {
  const { t } = useTranslation("casePage");
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
      setToast({ message: t("collaborators.collaboratorAdded") });
    } catch (e) {
      setToast({ type: "error", message: e.message });
    } finally {
      setBusy(false);
    }
  }
  async function remove(id) {
    if (!confirm(t("collaborators.confirmRemove"))) return;
    try {
      await removeCollaborator(caseId, id);
      await reload();
      setToast({ message: t("collaborators.collaboratorRemoved") });
    } catch (e) {
      setToast({ type: "error", message: e.message });
    }
  }
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>{t("collaborators.title")}</h2>
          <p>
            {t("collaborators.description")}
          </p>
        </div>
        {canManage ? (
          <button className="button button-primary" data-guide="add-collaborator" onClick={picker}>
            <UserPlus size={16} /> {t("collaborators.addCollaborator")}
          </button>
        ) : null}
      </div>
      <div className="collaborator-list">
        {collaborators.map((x) => (
          <div className="collaborator-row" key={x.user_id} data-guide="collaborator-row">
            <Avatar name={x.username} />
            <div className="collab-main">
              <strong>{x.username}</strong>
              <span>
                {x.role.replaceAll("_", " ")} · {x.clearance_level}
              </span>
            </div>
            <span className="muted small">
              {t("collaborators.addedBy", { name: x.assigned_by_username })}
              <br />
              {formatDate(x.assigned_at)}
            </span>
            {canRemove(x) ? (
              <button
                className="icon-button danger-icon" data-guide="remove-collaborator" aria-label={t("collaborators.removeAccessAria", { name: x.username })}
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
          title={t("collaborators.modalTitle")}
          onClose={() => setOpen(false)}
          footer={
            <>
              <button className="button" onClick={() => setOpen(false)}>
                {t("collaborators.cancel")}
              </button>
              <button
                className="button button-primary"
                disabled={!selected || busy}
                onClick={add}
              >
                {busy ? t("collaborators.adding") : t("collaborators.addCollaborator")}
              </button>
            </>
          }
        >
          <label className="field">
            <span>{t("collaborators.activeUser")}</span>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              <option value="">{t("collaborators.selectUser")}</option>
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.username} — {c.role} / {c.clearance_level}
                </option>
              ))}
            </select>
          </label>
          {clearanceWarning ? (
            <p className="warning-note section-spacer">
              {t("collaborators.clearanceWarning", {
                name: selectedCandidate.username,
                clearance: selectedCandidate.clearance_level,
              })}
            </p>
          ) : null}
        </Modal>
      ) : null}
    </section>
  );
}
function ConflictsTab({ caseId, statements, conflicts, reload, setToast }) {
  const { t } = useTranslation("casePage");
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
          ? t("timeline.candidatesFound", { count: created.length })
          : t("timeline.noCandidatesFound"),
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
              message: t("timeline.confirmedContradiction"),
            }
          : { message: t("timeline.statementConfirmed") },
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
      setToast({ message: t("timeline.suggestionDismissed") });
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
              message: t("timeline.contradictionDetected", {
                person: form.personName,
              }),
            }
          : { message: t("timeline.statementAdded") },
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
          <h2>{t("timeline.title")}</h2>
          <p>
            {t("timeline.description")}
          </p>
        </div>
        <div className="button-row">
          <button className="button" data-guide="timeline-scan" onClick={generate} disabled={generating}>
            {generating
              ? t("timeline.scanning")
              : t("timeline.scanButton")}
          </button>
          <button
            className="button button-primary"
            data-guide="timeline-add"
            onClick={() => setOpen(true)}
          >
            <UserPlus size={16} /> {t("timeline.addManually")}
          </button>
        </div>
      </div>

      {openConflicts.length ? (
        <div className="contradiction-list">
          {openConflicts.map((c) => (
            <div
              key={c.id}
              className="contradiction-sheet"
              data-guide="contradiction-card"
            >
              <div>
                <Badge tone="danger">{t("timeline.contradiction")}</Badge>
                <strong className="contradiction-person">
                  {c.person_name}
                </strong>
                <p className="small muted compact-copy">
                  {t("timeline.noValidSchedule")}
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
          title={t("timeline.emptyTitle")}
          description={t("timeline.emptyDescription")}
        />
      )}

      {suggested.length ? (
        <>
          <h3 className="review-heading">
            {t("timeline.systemExtracted")}
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
                    data-guide="suggestion-dismiss"
                    disabled={actingOn === s.id}
                    onClick={() => reject(s.id)}
                  >
                    {t("timeline.dismiss")}
                  </button>
                  <button
                    className="button button-primary"
                    data-guide="suggestion-confirm"
                    disabled={actingOn === s.id}
                    onClick={() => accept(s.id)}
                  >
                    {actingOn === s.id ? t("timeline.confirming") : t("timeline.confirm")}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : null}

      {confirmed.length ? (
        <>
          <h3 className="review-heading" data-guide="confirmed-statements">
            {t("timeline.confirmedStatements")}
          </h3>
          <div className="data-list confirmed-register">
            <div className="data-header">
              <span>{t("timeline.colPerson")}</span>
              <span>{t("timeline.colLocation")}</span>
              <span>{t("timeline.colWindow")}</span>
              <span>{t("timeline.colSource")}</span>
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
                <span className="small muted">{s.source_excerpt || t("timeline.noSource")}</span>
              </div>
            ))}
          </div>
        </>
      ) : null}

      {open ? (
        <Modal
          title={t("timeline.modalTitle")}
          onClose={() => setOpen(false)}
          footer={
            <>
              <button className="button" onClick={() => setOpen(false)}>
                {t("timeline.cancel")}
              </button>
              <button
                form="add-statement"
                className="button button-primary"
                disabled={busy}
              >
                {busy ? t("timeline.checking") : t("timeline.addAndCheck")}
              </button>
            </>
          }
        >
          <form id="add-statement" className="form-stack" onSubmit={submit}>
            <label className="field">
              <span>{t("timeline.fieldPerson")}</span>
              <input
                required
                value={form.personName}
                onChange={(e) =>
                  setForm({ ...form, personName: e.target.value })
                }
                placeholder={t("timeline.personPlaceholder")}
              />
            </label>
            <label className="field">
              <span>{t("timeline.fieldLocation")}</span>
              <input
                required
                value={form.locationName}
                onChange={(e) =>
                  setForm({ ...form, locationName: e.target.value })
                }
                placeholder={t("timeline.locationPlaceholder")}
              />
            </label>
            <label className="field">
              <span>{t("timeline.fieldWindowStart")}</span>
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
              <span>{t("timeline.fieldWindowEnd")}</span>
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
              <span>{t("timeline.fieldDuration")}</span>
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
              <span>{t("timeline.fieldSourceExcerpt")}</span>
              <input
                value={form.sourceExcerpt}
                onChange={(e) =>
                  setForm({ ...form, sourceExcerpt: e.target.value })
                }
                placeholder={t("timeline.sourcePlaceholder")}
              />
            </label>
          </form>
        </Modal>
      ) : null}
    </section>
  );
}
function AssistantTab({ caseId }) {
  const { t } = useTranslation("casePage");
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
            <h2>{t("assistant.title")}</h2>
            <p>
              {t("assistant.description")}
            </p>
          </div>
        </div>
        <div className="research-records">
          {messages.length === 0 ? (
            <p className="muted small">
              {t("assistant.noQuestionsYet")}
            </p>
          ) : null}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`research-entry ${m.role === "user" ? "research-query" : "research-answer"}`}
            >
              <span className="eyebrow">{m.role === "user" ? t("assistant.researchQuery") : t("assistant.generatedAnswer")}</span>
              {m.role === "user" ? m.text : <AssistantResponse>{m.text}</AssistantResponse>}
            </div>
          ))}
          {asking ? <div className="muted small">{t("assistant.thinking")}</div> : null}
        </div>
        <form onSubmit={ask} className="research-form" data-guide="assistant-ask">
          <div className="field grow">
            <input
              aria-label={t("assistant.researchQuestionAria")}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={t("assistant.questionPlaceholder")}
              disabled={asking}
            />
          </div>
          <button
            className="button button-primary"
            disabled={asking || !question.trim()}
          >
            {t("assistant.ask")}
          </button>
        </form>
        {error ? (
          <p className="form-error section-spacer">
            {error}
          </p>
        ) : null}
      </section>
      <aside className="stack">
        <section className="panel compact-panel" data-guide="gap-check">
          <h3>{t("assistant.gapCheckTitle")}</h3>
          <p className="muted small">
            {t("assistant.gapCheckDescription")}
          </p>
          {gapsError ? (
            <p className="form-error">{gapsError}</p>
          ) : gaps === null ? (
            <LoadingState label={t("assistant.checkingGaps")} />
          ) : gaps.length === 0 ? (
            <p className="muted small">{t("assistant.noGapsFound")}</p>
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
          <h3>{t("assistant.briefingTitle")}</h3>
          <button
            className="button button-block"
            data-guide="case-summary-btn"
            disabled={summarizing}
            onClick={generateSummary}
          >
            {summarizing ? t("assistant.generating") : t("assistant.generateSummary")}
          </button>
          {summary ? (
            <div
              className="small research-output"
            >
              <AssistantResponse>{summary}</AssistantResponse>
            </div>
          ) : null}
        </section>
        <section className="panel compact-panel">
          <h3>{t("assistant.legalTitle")}</h3>
          <p className="muted small warning-note">
            {t("assistant.legalWarning")}
          </p>
          <button
            className="button button-block"
            data-guide="legal-sections-btn"
            disabled={suggestingLegal}
            onClick={generateLegal}
          >
            {suggestingLegal ? t("assistant.analyzing") : t("assistant.suggestSections")}
          </button>
          {legal ? (
            <div
              className="small research-output"
            >
              <AssistantResponse>{legal}</AssistantResponse>
            </div>
          ) : null}
        </section>
      </aside>
    </div>
  );
}
function AuditTab({ audit }) {
  const { t } = useTranslation("casePage");
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
          <h2>{t("audit.title")}</h2>
          <p>{t("audit.description")}</p>
        </div>
        <div className="button-row" data-guide="audit-filters">
          <label className="field">
            <span className="small muted">{t("audit.actorDept")}</span>
            <select
              value={actorDept}
              onChange={(e) => setActorDept(e.target.value)}
            >
              {deptOptions("actor_department").map((d) => (
                <option key={d} value={d}>
                  {d === "ALL" ? t("audit.all") : d}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="small muted">{t("audit.evidenceDept")}</span>
            <select
              value={docDept}
              onChange={(e) => setDocDept(e.target.value)}
            >
              {deptOptions("document_department").map((d) => (
                <option key={d} value={d}>
                  {d === "ALL" ? t("audit.all") : d}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      {(actorDept !== "ALL" || docDept !== "ALL") && filtered.length === 0 ? (
        <div className="panel-empty">
          {t("audit.noEventsMatch")}
        </div>
      ) : null}
      <div className="audit-table" tabIndex={0} aria-label={t("audit.ariaScroll")}>
        <div className="audit-head">
          <span>{t("audit.colSequence")}</span>
          <span>{t("audit.colEvent")}</span>
          <span>{t("audit.colActor")}</span>
          <span>{t("audit.colResult")}</span>
          <span>{t("audit.colHash")}</span>
          <span>{t("audit.colTime")}</span>
        </div>
        {filtered.map((e) => (
          <div className="audit-row" key={e.sequence}>
            <code>{e.sequence}</code>
            <span>
              <strong>{e.action.replaceAll("_", " ")}</strong>
              {e.reason ? <small>{e.reason}</small> : null}
              {e.document_department ? (
                <small>{t("audit.evidenceDeptLabel", { dept: e.document_department })}</small>
              ) : null}
            </span>
            <span>
              {e.actor_username || t("audit.system")}
              {e.actor_department ? <small>{e.actor_department}</small> : null}
            </span>
            <Badge
              data-guide="audit-result"
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
            <details className="hash-disclosure" data-guide="audit-hash"><summary><code>{shortHash(e.entry_hash)}</code></summary><code className="wrap-code">{e.entry_hash}</code></details>
            <span className="small muted">{formatDate(e.timestamp)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
