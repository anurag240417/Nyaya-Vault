import { useEffect, useMemo, useState } from 'react';
import { Navigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
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
function departmentLabel(t, d) {
  if (!d) return t('departments.unassigned');
  return t(`departments.${d}`, { defaultValue: d });
}

function clearanceLabel(t, clearance) {
  if (!clearance) return clearance;
  return t(`clearances.${clearance}`, { defaultValue: clearance });
}

function roleLabel(t, role) {
  if (!role) return t('roles.unknown');
  return t(`roles.${role}`, { defaultValue: role.replaceAll('_', ' ') });
}

export default function AdminPage() {
  const { t } = useTranslation('admin');
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
      setToast({ message: t('users.saveSuccess') });
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
      setToast({ type: 'error', message: t('caseAssignment.selectPrimaryError') });
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
      setToast({ message: t('caseAssignment.createSuccess') });
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
      setToast({ message: t('caseAssignment.assignmentsUpdated', { caseNumber: updated.case_number }) });
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
      setToast({ message: t('caseAssignment.collaboratorRemoved') });
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
          <p className="eyebrow">{t('page.eyebrow')}</p><h1>{t('page.title')}</h1>
          <p>{t('page.subtitle')}</p>
        </div>
      </div>

      <div className="admin-tabs" role="group" aria-label={t('tabs.ariaLabel')}>
        <button className={tab === 'users' ? 'active' : ''} onClick={() => setTab('users')}>
          <UserCog size={16} /> {t('tabs.users')}
        </button>
        <button className={tab === 'cases' ? 'active' : ''} onClick={() => setTab('cases')}>
          <BriefcaseBusiness size={16} /> {t('tabs.cases')}
        </button>
      </div>

      {tab === 'users' ? (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2><UserCog size={18} /> {t('users.heading')}</h2>
              <p>{t('users.description')}</p>
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
                    aria-label={t('users.roleAriaLabel', { username: user.username })}
                    value={draft.role || user.role}
                    onChange={(event) => setDrafts({
                      ...drafts,
                      [user.id]: { ...draft, role: event.target.value },
                    })}
                  >
                    {ROLES.map((role) => <option key={role} value={role}>{roleLabel(t, role)}</option>)}
                  </select>
                  <select
                    aria-label={t('users.clearanceAriaLabel', { username: user.username })}
                    value={draft.clearance_level || user.clearance_level}
                    onChange={(event) => setDrafts({
                      ...drafts,
                      [user.id]: { ...draft, clearance_level: event.target.value },
                    })}
                  >
                    {CLEARANCES.map((clearance) => <option key={clearance} value={clearance}>{clearanceLabel(t, clearance)}</option>)}
                  </select>
                  <select
                    aria-label={t('users.departmentAriaLabel', { username: user.username })}
                    value={draft.department ?? (user.department || '')}
                    onChange={(event) => setDrafts({
                      ...drafts,
                      [user.id]: { ...draft, department: event.target.value },
                    })}
                    title={t('users.departmentTitle')}
                  >
                    {DEPARTMENTS.map((d) => <option key={d || 'unassigned'} value={d}>{departmentLabel(t, d)}</option>)}
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
                    {draft.is_active ? t('users.active') : t('users.disabled')}
                  </label>
                  <Badge tone={clearanceTone(draft.clearance_level)}>{clearanceLabel(t, draft.clearance_level)}</Badge>
                  <Badge tone={departmentTone(draft.department)}>{departmentLabel(t, draft.department)}</Badge>
                  <button className="button button-sm" onClick={() => saveUser(user.id)}>
                    <Save size={14} /> {t('actions.save')}
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
              <div><strong>{cases.length}</strong><span>{t('summary.totalCases')}</span></div>
            </div>
            <div className="admin-summary-card">
              <ShieldCheck size={18} />
              <div><strong>{investigators.length}</strong><span>{t('summary.activeInvestigators')}</span></div>
            </div>
            <div className="admin-summary-card">
              <Users size={18} />
              <div><strong>{activeUsers.length}</strong><span>{t('summary.activeUsers')}</span></div>
            </div>
          </div>

          <section className="panel">
            <div className="panel-header admin-case-header">
              <div>
                <h2><BriefcaseBusiness size={18} /> {t('caseAssignment.heading')}</h2>
                <p>{t('caseAssignment.description')}</p>
              </div>
              <button
                className="button button-primary"
                onClick={() => setCreateOpen(true)}
                disabled={!investigators.length}
                title={!investigators.length ? t('caseAssignment.createDisabledTitle', { role: t('roles.INVESTIGATING_OFFICER') }) : undefined}
              >
                <Plus size={16} /> {t('caseAssignment.createButton')}
              </button>
            </div>

            <div className="admin-case-toolbar">
              <div className="search-input">
                <Search size={16} />
                <input
                  value={caseQuery}
                  onChange={(event) => setCaseQuery(event.target.value)}
                  aria-label={t('caseAssignment.searchAriaLabel')} placeholder={t('caseAssignment.searchPlaceholder')}
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
                          <span className="visibility-pill">{t('caseAssignment.visibilityPrivate')}</span>
                        </div>
                        <h3>{item.title}</h3>
                        <p>{item.description || t('caseAssignment.noDescription')}</p>
                        <span className="admin-case-created">{t('caseAssignment.createdOn', { date: formatDate(item.created_at) })}</span>
                      </div>

                      <div className="admin-assignment-column">
                        <span className="tiny-label">{t('caseAssignment.primaryInvestigatorLabel')}</span>
                        {item.primary_investigator ? (
                          <div className="admin-primary-person">
                            <Avatar name={item.primary_investigator.username} />
                            <div>
                              <strong>{item.primary_investigator.username}</strong>
                              <span>{roleLabel(t, item.primary_investigator.role)}</span>
                            </div>
                          </div>
                        ) : <span className="admin-unassigned">{t('caseAssignment.notAssigned')}</span>}
                      </div>

                      <div className="admin-assignment-column">
                        <span className="tiny-label">{t('caseAssignment.collaboratorsLabel')}</span>
                        <div className="admin-collaborator-chips">
                          {visibleCollaborators.length ? visibleCollaborators.slice(0, 5).map((collaborator) => (
                            <span className="admin-collaborator-chip" key={collaborator.user_id}>
                              {collaborator.username}
                              <button
                                type="button"
                                disabled={busy}
                                title={t('caseAssignment.removeCollaboratorTitle', { username: collaborator.username })}
                                onClick={() => removeAdditionalCollaborator(item, collaborator.user_id)}
                              >
                                <Trash2 size={12} />
                              </button>
                            </span>
                          )) : <span className="admin-unassigned">{t('caseAssignment.noCollaborators')}</span>}
                          {visibleCollaborators.length > 5 ? (
                            <span className="admin-more-chip">{t('caseAssignment.moreCount', { count: visibleCollaborators.length - 5 })}</span>
                          ) : null}
                        </div>
                      </div>

                      <div className="admin-case-actions">
                        <button className="button button-sm" onClick={() => openManage(item)}>
                          <Users size={14} /> {t('caseAssignment.manageButton')}
                        </button>
                        <Link className="button button-sm" to={`/cases/${item.id}`}>
                          {t('caseAssignment.openButton')} <ChevronRight size={14} />
                        </Link>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <EmptyState
                icon={<BriefcaseBusiness size={28} />}
                title={t('caseAssignment.emptyTitle')}
                description={caseQuery ? t('caseAssignment.emptySearchDescription') : t('caseAssignment.emptyDefaultDescription')}
                action={!caseQuery && investigators.length ? (
                  <button className="button button-primary" onClick={() => setCreateOpen(true)}>
                    <Plus size={15} /> {t('caseAssignment.createCaseButton')}
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
          title={t('createModal.title')}
          onClose={() => !busy && setCreateOpen(false)}
          footer={(
            <>
              <button className="button" disabled={busy} onClick={() => setCreateOpen(false)}>{t('actions.cancel')}</button>
              <button className="button button-primary" form="admin-create-case" disabled={busy}>
                {busy ? t('createModal.creating') : t('createModal.submit')}
              </button>
            </>
          )}
        >
          <form id="admin-create-case" className="form-stack" onSubmit={submitCreateCase}>
            <div className="admin-form-grid">
              <label className="field">
                <span>{t('createModal.caseNumberLabel')}</span>
                <input
                  required
                  value={createForm.case_number}
                  onChange={(event) => setCreateForm({ ...createForm, case_number: event.target.value })}
                  placeholder={t('createModal.caseNumberPlaceholder')}
                />
              </label>
              <label className="field">
                <span>{t('createModal.primaryInvestigatorLabel')}</span>
                <select
                  required
                  value={createForm.primary_investigator_id}
                  onChange={(event) => setCreateForm({
                    ...createForm,
                    primary_investigator_id: event.target.value,
                    collaborator_ids: createForm.collaborator_ids.filter((id) => id !== event.target.value),
                  })}
                >
                  <option value="">{t('createModal.selectInvestigatorOption')}</option>
                  {investigators.map((user) => (
                    <option key={user.id} value={user.id}>{user.username} — {user.email}</option>
                  ))}
                </select>
              </label>
            </div>
            <label className="field">
              <span>{t('createModal.titleLabel')}</span>
              <input
                required
                value={createForm.title}
                onChange={(event) => setCreateForm({ ...createForm, title: event.target.value })}
                placeholder={t('createModal.titlePlaceholder')}
              />
            </label>
            <label className="field">
              <span>{t('createModal.descriptionLabel')}</span>
              <textarea
                rows="4"
                maxLength="5000"
                value={createForm.description}
                onChange={(event) => setCreateForm({ ...createForm, description: event.target.value })}
                placeholder={t('createModal.descriptionPlaceholder')}
              />
            </label>
            <div className="admin-picker-block">
              <div className="admin-picker-heading">
                <div>
                  <strong>{t('createModal.collaboratorsHeading')}</strong>
                  <span>{t('createModal.collaboratorsSubtext')}</span>
                </div>
                <Badge>{t('createModal.selectedCount', { count: createForm.collaborator_ids.length })}</Badge>
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
                        <span><strong>{user.username}</strong><small>{roleLabel(t, user.role)}</small></span>
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
          title={t('manageModal.title', { caseNumber: manageCase.case_number })}
          onClose={() => !busy && setManageCase(null)}
          footer={(
            <>
              <button className="button" disabled={busy} onClick={() => setManageCase(null)}>{t('actions.cancel')}</button>
              <button className="button button-primary" disabled={busy} onClick={saveAssignments}>
                <Save size={15} /> {busy ? t('manageModal.saving') : t('manageModal.submit')}
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
              <span>{t('manageModal.primaryInvestigatorLabel')}</span>
              <select
                value={assignmentForm.primary_investigator_id}
                onChange={(event) => changePrimaryInvestigator(event.target.value)}
              >
                <option value="">{t('manageModal.noPrimaryOption')}</option>
                {investigators.map((user) => (
                  <option key={user.id} value={user.id}>{user.username} — {user.email}</option>
                ))}
              </select>
            </label>
            <div className="admin-picker-block">
              <div className="admin-picker-heading">
                <div>
                  <strong>{t('manageModal.collaboratorsHeading')}</strong>
                  <span>{t('manageModal.collaboratorsSubtext')}</span>
                </div>
                <Badge>{t('manageModal.additionalCount', { count: assignmentForm.collaborator_ids.length })}</Badge>
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
                        <span><strong>{user.username}</strong><small>{roleLabel(t, user.role)}</small></span>
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
