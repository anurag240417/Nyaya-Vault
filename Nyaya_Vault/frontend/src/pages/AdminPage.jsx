import { useEffect, useMemo, useState } from 'react';
import { Navigate, Link } from 'react-router-dom';
import {
  BriefcaseBusiness,
  Check,
  ChevronRight,
  Plus,
  Save,
  Search,
  ShieldCheck,
  Trash2,
  UserCog,
  Users,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  adminCreateCase,
  adminListCases,
  adminReplaceCaseAssignments,
  adminUpdateProfile,
  listProfiles,
} from '../lib/api';
import { formatDate } from '../lib/format';
import Avatar from '../components/Avatar';
import Badge, { clearanceTone, departmentTone } from '../components/Badge';
import EmptyState from '../components/EmptyState';
import LoadingState from '../components/LoadingState';
import Modal from '../components/Modal';
import Toast from '../components/Toast';

const ROLES = ['ADMIN', 'INVESTIGATING_OFFICER', 'PROSECUTOR', 'JUDGE', 'CLERK'];
const CLEARANCES = ['PUBLIC', 'RESTRICTED', 'CONFIDENTIAL', 'SECRET'];
const DEPARTMENTS = ['', 'GENERAL', 'POLICE', 'FORENSICS', 'PROSECUTION', 'JUDICIARY'];
function departmentLabel(d) { return d || 'Unassigned'; }

function cleanRole(role) {
  return role?.replaceAll('_', ' ') || 'Unknown role';
}

export default function AdminPage() {
  const { profile } = useAuth();
  const [tab, setTab] = useState('users');
  const [users, setUsers] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [caseLoading, setCaseLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [caseQuery, setCaseQuery] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [manageCase, setManageCase] = useState(null);
  const [busy, setBusy] = useState(false);
  const [createForm, setCreateForm] = useState({
    case_number: '',
    title: '',
    description: '',
    primary_investigator_id: '',
    collaborator_ids: [],
  });
  const [assignmentForm, setAssignmentForm] = useState({
    primary_investigator_id: '',
    collaborator_ids: [],
  });

  async function reloadUsers() {
    const rows = await listProfiles();
    setUsers(rows);
    setDrafts(
      Object.fromEntries(
        rows.map((user) => [
          user.id,
          {
            role: user.role,
            clearance_level: user.clearance_level,
            department: user.department || '',
            is_active: user.is_active,
          },
        ]),
      ),
    );
    return rows;
  }

  async function reloadCases() {
    setCaseLoading(true);
    try {
      setCases(await adminListCases());
    } finally {
      setCaseLoading(false);
    }
  }

  useEffect(() => {
    if (profile?.role === 'ADMIN') {
      Promise.all([reloadUsers(), reloadCases()]).finally(() => setLoading(false));
    } else if (profile) {
      setLoading(false);
    }
  }, [profile]);

  const activeUsers = useMemo(() => users.filter((user) => user.is_active), [users]);
  const investigators = useMemo(
    () => activeUsers.filter((user) => user.role === 'INVESTIGATING_OFFICER'),
    [activeUsers],
  );
  const filteredCases = useMemo(() => {
    const q = caseQuery.trim().toLowerCase();
    if (!q) return cases;
    return cases.filter((item) => {
      const collaborators = (item.collaborators || []).map((c) => `${c.username} ${c.email || ''}`).join(' ');
      return `${item.case_number} ${item.title} ${item.description || ''} ${collaborators}`
        .toLowerCase()
        .includes(q);
    });
  }, [cases, caseQuery]);

  if (profile && profile.role !== 'ADMIN') return <Navigate to="/dashboard" replace />;
  if (loading) return <LoadingState />;

  async function saveUser(id) {
    const draft = drafts[id];
    try {
      await adminUpdateProfile(id, draft.role, draft.clearance_level, draft.is_active, draft.department || null);
      await reloadUsers();
      setToast({ message: 'User permissions updated.' });
    } catch (error) {
      setToast({ type: 'error', message: error.message });
    }
  }

  function toggleCreateCollaborator(userId) {
    setCreateForm((current) => ({
      ...current,
      collaborator_ids: current.collaborator_ids.includes(userId)
        ? current.collaborator_ids.filter((id) => id !== userId)
        : [...current.collaborator_ids, userId],
    }));
  }

  function openManage(item) {
    const primaryId = item.primary_investigator_id || item.primary_investigator?.id || '';
    const additional = (item.collaborators || [])
      .map((collaborator) => collaborator.user_id)
      .filter((id) => id !== item.created_by && id !== primaryId);
    setAssignmentForm({
      primary_investigator_id: primaryId,
      collaborator_ids: additional,
    });
    setManageCase(item);
  }

  function changePrimaryInvestigator(userId) {
    setAssignmentForm((current) => ({
      primary_investigator_id: userId,
      collaborator_ids: current.collaborator_ids.filter((id) => id !== userId),
    }));
  }

  function toggleAssignmentCollaborator(userId) {
    setAssignmentForm((current) => ({
      ...current,
      collaborator_ids: current.collaborator_ids.includes(userId)
        ? current.collaborator_ids.filter((id) => id !== userId)
        : [...current.collaborator_ids, userId],
    }));
  }

  async function submitCreateCase(event) {
    event.preventDefault();
    if (!createForm.primary_investigator_id) {
      setToast({ type: 'error', message: 'Select a primary investigating officer.' });
      return;
    }
    setBusy(true);
    try {
      await adminCreateCase({
        ...createForm,
        collaborator_ids: createForm.collaborator_ids.filter(
          (id) => id !== createForm.primary_investigator_id,
        ),
      });
      setCreateForm({
        case_number: '',
        title: '',
        description: '',
        primary_investigator_id: '',
        collaborator_ids: [],
      });
      setCreateOpen(false);
      await reloadCases();
      setToast({ message: 'Case created and assignments saved.' });
    } catch (error) {
      setToast({ type: 'error', message: error.message });
    } finally {
      setBusy(false);
    }
  }

  async function saveAssignments() {
    if (!manageCase) return;
    setBusy(true);
    try {
      const updated = await adminReplaceCaseAssignments(manageCase.id, {
        primary_investigator_id: assignmentForm.primary_investigator_id || null,
        collaborator_ids: assignmentForm.collaborator_ids.filter(
          (id) => id !== assignmentForm.primary_investigator_id,
        ),
      });
      setManageCase(null);
      await reloadCases();
      setToast({ message: `Assignments updated for ${updated.case_number}.` });
    } catch (error) {
      setToast({ type: 'error', message: error.message });
    } finally {
      setBusy(false);
    }
  }

  async function removeAdditionalCollaborator(item, userId) {
    const primaryId = item.primary_investigator_id || item.primary_investigator?.id || null;
    const additional = (item.collaborators || [])
      .map((collaborator) => collaborator.user_id)
      .filter((id) => id !== item.created_by && id !== primaryId && id !== userId);
    setBusy(true);
    try {
      await adminReplaceCaseAssignments(item.id, {
        primary_investigator_id: primaryId,
        collaborator_ids: additional,
      });
      await reloadCases();
      setToast({ message: 'Collaborator removed.' });
    } catch (error) {
      setToast({ type: 'error', message: error.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page admin-page">
      <div className="page-title-row">
        <div>
          <p className="eyebrow">Administration</p><h1>System Registry & Case Assignment Office</h1>
          <p>Manage users, case ownership, investigating officers, collaborators, and access state.</p>
        </div>
      </div>

      <div className="admin-tabs" role="group" aria-label="Administration sections">
        <button className={tab === 'users' ? 'active' : ''} onClick={() => setTab('users')}>
          <UserCog size={16} /> Personnel Register
        </button>
        <button className={tab === 'cases' ? 'active' : ''} onClick={() => setTab('cases')}>
          <BriefcaseBusiness size={16} /> Case Assignment Register
        </button>
      </div>

      {tab === 'users' ? (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2><UserCog size={18} /> Personnel Register</h2>
              <p>Security-sensitive controls: changes to role, clearance, department, and account state affect access.</p>
            </div>
          </div>
          <div className="admin-user-list">
            {users.map((user) => {
              const draft = drafts[user.id] || {};
              return (
                <div className="admin-user-row" key={user.id}>
                  <Avatar name={user.username} />
                  <div className="admin-user-info">
                    <strong>{user.username}</strong>
                    <span>{user.email}</span>
                  </div>
                  <select
                    aria-label={`Role for ${user.username}`}
                    value={draft.role || user.role}
                    onChange={(event) => setDrafts({
                      ...drafts,
                      [user.id]: { ...draft, role: event.target.value },
                    })}
                  >
                    {ROLES.map((role) => <option key={role}>{role}</option>)}
                  </select>
                  <select
                    aria-label={`Clearance for ${user.username}`}
                    value={draft.clearance_level || user.clearance_level}
                    onChange={(event) => setDrafts({
                      ...drafts,
                      [user.id]: { ...draft, clearance_level: event.target.value },
                    })}
                  >
                    {CLEARANCES.map((clearance) => <option key={clearance}>{clearance}</option>)}
                  </select>
                  <select
                    aria-label={`Department for ${user.username}`}
                    value={draft.department ?? (user.department || '')}
                    onChange={(event) => setDrafts({
                      ...drafts,
                      [user.id]: { ...draft, department: event.target.value },
                    })}
                    title="Only an admin can set a user's department; a document tagged for a department is only visible to matching users."
                  >
                    {DEPARTMENTS.map((d) => <option key={d || 'unassigned'} value={d}>{departmentLabel(d)}</option>)}
                  </select>
                  <label className="switch-label">
                    <input
                      type="checkbox"
                      checked={Boolean(draft.is_active)}
                      onChange={(event) => setDrafts({
                        ...drafts,
                        [user.id]: { ...draft, is_active: event.target.checked },
                      })}
                    />
                    {draft.is_active ? 'Active' : 'Disabled'}
                  </label>
                  <Badge tone={clearanceTone(draft.clearance_level)}>{draft.clearance_level}</Badge>
                  <Badge tone={departmentTone(draft.department)}>{departmentLabel(draft.department)}</Badge>
                  <button className="button button-sm" onClick={() => saveUser(user.id)}>
                    <Save size={14} /> Save
                  </button>
                </div>
              );
            })}
          </div>
        </section>
      ) : (
        <>
          <div className="admin-case-summary-grid">
            <div className="admin-summary-card">
              <BriefcaseBusiness size={18} />
              <div><strong>{cases.length}</strong><span>Total cases</span></div>
            </div>
            <div className="admin-summary-card">
              <ShieldCheck size={18} />
              <div><strong>{investigators.length}</strong><span>Active investigators</span></div>
            </div>
            <div className="admin-summary-card">
              <Users size={18} />
              <div><strong>{activeUsers.length}</strong><span>Active users</span></div>
            </div>
          </div>

          <section className="panel">
            <div className="panel-header admin-case-header">
              <div>
                <h2><BriefcaseBusiness size={18} /> Case Assignment Register</h2>
                <p>Create cases, choose the primary investigator, and control the complete collaborator set.</p>
              </div>
              <button
                className="button button-primary"
                onClick={() => setCreateOpen(true)}
                disabled={!investigators.length}
                title={!investigators.length ? 'Create or activate an INVESTIGATING_OFFICER first.' : undefined}
              >
                <Plus size={16} /> Create & assign case
              </button>
            </div>

            <div className="admin-case-toolbar">
              <div className="search-input">
                <Search size={16} />
                <input
                  value={caseQuery}
                  onChange={(event) => setCaseQuery(event.target.value)}
                  aria-label="Search managed cases" placeholder="Search cases, investigators, or collaborators…"
                />
              </div>
            </div>

            {caseLoading ? <LoadingState /> : filteredCases.length ? (
              <div className="admin-case-list">
                {filteredCases.map((item) => {
                  const primaryId = item.primary_investigator_id || item.primary_investigator?.id || null;
                  const visibleCollaborators = (item.collaborators || []).filter(
                    (collaborator) => collaborator.user_id !== item.created_by && collaborator.user_id !== primaryId,
                  );
                  return (
                    <article className="admin-case-row" key={item.id}>
                      <div className="admin-case-main">
                        <div className="admin-case-title-line">
                          <Link to={`/cases/${item.id}`}>{item.case_number}</Link>
                          <span className="visibility-pill">Private</span>
                        </div>
                        <h3>{item.title}</h3>
                        <p>{item.description || 'No description has been added.'}</p>
                        <span className="admin-case-created">Created {formatDate(item.created_at)}</span>
                      </div>

                      <div className="admin-assignment-column">
                        <span className="tiny-label">PRIMARY INVESTIGATOR</span>
                        {item.primary_investigator ? (
                          <div className="admin-primary-person">
                            <Avatar name={item.primary_investigator.username} />
                            <div>
                              <strong>{item.primary_investigator.username}</strong>
                              <span>{cleanRole(item.primary_investigator.role)}</span>
                            </div>
                          </div>
                        ) : <span className="admin-unassigned">Not assigned</span>}
                      </div>

                      <div className="admin-assignment-column">
                        <span className="tiny-label">COLLABORATORS</span>
                        <div className="admin-collaborator-chips">
                          {visibleCollaborators.length ? visibleCollaborators.slice(0, 5).map((collaborator) => (
                            <span className="admin-collaborator-chip" key={collaborator.user_id}>
                              {collaborator.username}
                              <button
                                type="button"
                                disabled={busy}
                                title={`Remove ${collaborator.username}`}
                                onClick={() => removeAdditionalCollaborator(item, collaborator.user_id)}
                              >
                                <Trash2 size={12} />
                              </button>
                            </span>
                          )) : <span className="admin-unassigned">No additional collaborators</span>}
                          {visibleCollaborators.length > 5 ? (
                            <span className="admin-more-chip">+{visibleCollaborators.length - 5} more</span>
                          ) : null}
                        </div>
                      </div>

                      <div className="admin-case-actions">
                        <button className="button button-sm" onClick={() => openManage(item)}>
                          <Users size={14} /> Manage assignments
                        </button>
                        <Link className="button button-sm" to={`/cases/${item.id}`}>
                          Open <ChevronRight size={14} />
                        </Link>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <EmptyState
                icon={<BriefcaseBusiness size={28} />}
                title="No managed cases found"
                description={caseQuery ? 'Try a different search.' : 'Create the first case and assign an investigating officer.'}
                action={!caseQuery && investigators.length ? (
                  <button className="button button-primary" onClick={() => setCreateOpen(true)}>
                    <Plus size={15} /> Create case
                  </button>
                ) : null}
              />
            )}
          </section>
        </>
      )}

      {createOpen ? (
        <Modal
          width="780px"
          title="Create and assign case"
          onClose={() => !busy && setCreateOpen(false)}
          footer={(
            <>
              <button className="button" disabled={busy} onClick={() => setCreateOpen(false)}>Cancel</button>
              <button className="button button-primary" form="admin-create-case" disabled={busy}>
                {busy ? 'Creating…' : 'Create & assign'}
              </button>
            </>
          )}
        >
          <form id="admin-create-case" className="form-stack" onSubmit={submitCreateCase}>
            <div className="admin-form-grid">
              <label className="field">
                <span>Case number</span>
                <input
                  required
                  value={createForm.case_number}
                  onChange={(event) => setCreateForm({ ...createForm, case_number: event.target.value })}
                  placeholder="FIR-2026-00124"
                />
              </label>
              <label className="field">
                <span>Primary investigating officer</span>
                <select
                  required
                  value={createForm.primary_investigator_id}
                  onChange={(event) => setCreateForm({
                    ...createForm,
                    primary_investigator_id: event.target.value,
                    collaborator_ids: createForm.collaborator_ids.filter((id) => id !== event.target.value),
                  })}
                >
                  <option value="">Select investigator…</option>
                  {investigators.map((user) => (
                    <option key={user.id} value={user.id}>{user.username} — {user.email}</option>
                  ))}
                </select>
              </label>
            </div>
            <label className="field">
              <span>Title</span>
              <input
                required
                value={createForm.title}
                onChange={(event) => setCreateForm({ ...createForm, title: event.target.value })}
                placeholder="Investigation title"
              />
            </label>
            <label className="field">
              <span>Description</span>
              <textarea
                rows="4"
                maxLength="5000"
                value={createForm.description}
                onChange={(event) => setCreateForm({ ...createForm, description: event.target.value })}
                placeholder="Case scope, notes, or brief…"
              />
            </label>
            <div className="admin-picker-block">
              <div className="admin-picker-heading">
                <div>
                  <strong>Additional collaborators</strong>
                  <span>Select any active users who should immediately have case access.</span>
                </div>
                <Badge>{createForm.collaborator_ids.length} selected</Badge>
              </div>
              <div className="admin-user-picker">
                {activeUsers
                  .filter((user) => user.id !== profile.id && user.id !== createForm.primary_investigator_id)
                  .map((user) => {
                    const selected = createForm.collaborator_ids.includes(user.id);
                    return (
                      <button
                        type="button"
                        key={user.id}
                        aria-pressed={selected} className={`admin-picker-user ${selected ? 'selected' : ''}`}
                        onClick={() => toggleCreateCollaborator(user.id)}
                      >
                        <Avatar name={user.username} />
                        <span><strong>{user.username}</strong><small>{cleanRole(user.role)}</small></span>
                        <span className="admin-picker-check">{selected ? <Check size={15} /> : null}</span>
                      </button>
                    );
                  })}
              </div>
            </div>
          </form>
        </Modal>
      ) : null}

      {manageCase ? (
        <Modal
          width="760px"
          title={`Manage assignments · ${manageCase.case_number}`}
          onClose={() => !busy && setManageCase(null)}
          footer={(
            <>
              <button className="button" disabled={busy} onClick={() => setManageCase(null)}>Cancel</button>
              <button className="button button-primary" disabled={busy} onClick={saveAssignments}>
                <Save size={15} /> {busy ? 'Saving…' : 'Save assignments'}
              </button>
            </>
          )}
        >
          <div className="form-stack">
            <div className="admin-case-modal-summary">
              <BriefcaseBusiness size={18} />
              <div><strong>{manageCase.title}</strong><span>{manageCase.case_number}</span></div>
            </div>
            <label className="field">
              <span>Primary investigating officer</span>
              <select
                value={assignmentForm.primary_investigator_id}
                onChange={(event) => changePrimaryInvestigator(event.target.value)}
              >
                <option value="">No primary investigator</option>
                {investigators.map((user) => (
                  <option key={user.id} value={user.id}>{user.username} — {user.email}</option>
                ))}
              </select>
            </label>
            <div className="admin-picker-block">
              <div className="admin-picker-heading">
                <div>
                  <strong>Assigned collaborators</strong>
                  <span>The case creator is retained automatically. Select the additional users who should remain assigned.</span>
                </div>
                <Badge>{assignmentForm.collaborator_ids.length} additional</Badge>
              </div>
              <div className="admin-user-picker">
                {activeUsers
                  .filter((user) => user.id !== manageCase.created_by && user.id !== assignmentForm.primary_investigator_id)
                  .map((user) => {
                    const selected = assignmentForm.collaborator_ids.includes(user.id);
                    return (
                      <button
                        type="button"
                        key={user.id}
                        aria-pressed={selected} className={`admin-picker-user ${selected ? 'selected' : ''}`}
                        onClick={() => toggleAssignmentCollaborator(user.id)}
                      >
                        <Avatar name={user.username} />
                        <span><strong>{user.username}</strong><small>{cleanRole(user.role)}</small></span>
                        <span className="admin-picker-check">{selected ? <Check size={15} /> : null}</span>
                      </button>
                    );
                  })}
              </div>
            </div>
          </div>
        </Modal>
      ) : null}

      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
