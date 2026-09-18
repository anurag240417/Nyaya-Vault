import { supabase } from './supabase';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

async function accessToken() {
  const { data, error } = await supabase.auth.getSession();
  if (error) throw error;
  return data.session?.access_token || null;
}

function messageFrom(body, status) {
  if (body && typeof body === 'object') return body.detail || body.error || body.message || `HTTP ${status}`;
  return typeof body === 'string' && body ? body : `HTTP ${status}`;
}

export async function apiFetchRaw(path, options = {}, retry = true) {
  let token = await accessToken();
  if (!token) throw new Error('No authenticated session.');
  const headers = new Headers(options.headers || {});
  headers.set('Authorization', `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  let response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (response.status === 401 && retry) {
    const { data, error } = await supabase.auth.refreshSession();
    if (!error && data.session?.access_token) {
      token = data.session.access_token;
      headers.set('Authorization', `Bearer ${token}`);
      response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    }
  }
  if (!response.ok) {
    const text = await response.text();
    let body = text;
    try { body = text ? JSON.parse(text) : null; } catch { /* keep text */ }
    const err = new Error(messageFrom(body, response.status));
    if (body && typeof body === 'object') {
      err.code = body.code;
      err.details = body.details;
    }
    throw err;
  }
  return response;
}

async function apiJson(path, options = {}) {
  const response = await apiFetchRaw(path, options);
  if (response.status === 204) return null;
  return response.json();
}

export async function getMyProfile() { return apiJson('/api/v1/auth/me'); }
export async function recordLoginEvent() { return apiJson('/api/v1/auth/login-event', { method: 'POST' }); }

export async function listCases() { return apiJson('/api/v1/cases'); }
export async function getCase(caseId) { return apiJson(`/api/v1/cases/${caseId}`); }
export async function createCase(payload) { return apiJson('/api/v1/cases', { method: 'POST', body: JSON.stringify(payload) }); }
export async function updateCase(caseId, payload) { return apiJson(`/api/v1/cases/${caseId}`, { method: 'PATCH', body: JSON.stringify(payload) }); }

export async function getCaseCollaborators(caseId) { return apiJson(`/api/v1/cases/${caseId}/collaborators`); }
export async function listCollaboratorCandidates(caseId) { return apiJson(`/api/v1/cases/${caseId}/collaborator-candidates`); }
export async function addCollaborator(caseId, userId) { return apiJson(`/api/v1/cases/${caseId}/collaborators`, { method: 'POST', body: JSON.stringify({ user_id: userId }) }); }
export async function removeCollaborator(caseId, userId) { return apiJson(`/api/v1/cases/${caseId}/collaborators/${userId}`, { method: 'DELETE' }); }

export async function listCaseDocuments(caseId) { return apiJson(`/api/v1/cases/${caseId}/documents`); }
export async function getDocument(documentId) { return apiJson(`/api/v1/documents/${documentId}`); }
export async function listDocumentVersions(documentId) { return apiJson(`/api/v1/documents/${documentId}/versions`); }
export async function getLatestVersionData(doc) { return apiJson(`/api/v1/documents/${doc.id}/versions/latest`); }

function validateUpload(file) {
  const allowed = new Set([
    'application/pdf', 'image/jpeg', 'image/png', 'image/tiff',
    'video/mp4', 'video/quicktime', 'video/webm',
  ]);
  if (!file) throw new Error('Choose a file.');
  if (!allowed.has(file.type)) throw new Error(`Unsupported file type: ${file.type || 'unknown'}`);
  if (file.size <= 0) throw new Error('Empty files cannot be uploaded.');
  // This is a fast client-side check only - the backend's own MAX_UPLOAD_BYTES
  // setting is what's actually enforced (currently 25MB by default; raise it
  // there via env var if you need larger video files, remembering the whole
  // file is read into server memory per upload before storage).
  if (file.size > 200 * 1024 * 1024) throw new Error('File exceeds the 200 MB limit.');
}

export async function uploadNewDocument({ caseId, title, documentType, clearanceLevel, file, department }) {
  validateUpload(file);
  const body = new FormData();
  body.append('title', title);
  body.append('document_type', documentType || '');
  body.append('clearance_level', clearanceLevel);
  body.append('department', department || 'GENERAL');
  body.append('file', file);
  return apiJson(`/api/v1/cases/${caseId}/documents`, { method: 'POST', body });
}

export async function uploadDocumentVersion({ document, file, changeSummary }) {
  validateUpload(file);
  const body = new FormData();
  body.append('change_summary', changeSummary || '');
  body.append('file', file);
  return apiJson(`/api/v1/documents/${document.id}/versions`, { method: 'POST', body });
}

export async function getVersionObjectUrl(documentId, version) {
  const response = await apiFetchRaw(`/api/v1/documents/${documentId}/versions/${version.id}/download`);
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

export async function downloadDocumentVersion(documentId, version) {
  const url = await getVersionObjectUrl(documentId, version);
  const anchor = window.document.createElement('a');
  anchor.href = url;
  anchor.download = (version.storage_key || `document-v${version.version_number}`).split('/').pop();
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function getEntities(versionId) { return apiJson(`/api/v1/document-versions/${versionId}/entities`); }
export async function confirmEntities(documentId, confirmedIds, rejectedIds) {
  return apiJson(`/api/v1/documents/${documentId}/entities/review`, {
    method: 'POST', body: JSON.stringify({ confirmed_ids: confirmedIds, rejected_ids: rejectedIds }),
  });
}
export async function getRedactions(versionId) { return apiJson(`/api/v1/document-versions/${versionId}/redactions`); }
export async function confirmRedactions(documentId, approvedIds, rejectedIds) {
  return apiJson(`/api/v1/documents/${documentId}/redactions/review`, {
    method: 'POST', body: JSON.stringify({ approved_ids: approvedIds, rejected_ids: rejectedIds }),
  });
}

export async function getCaseAudit(caseId) { return apiJson(`/api/v1/cases/${caseId}/audit`); }
export async function getRecentActivity(limit = 12) { return apiJson(`/api/v1/activity?limit=${encodeURIComponent(limit)}`); }
export async function searchCaseVault(query, caseId = null) {
  if (!query.trim()) return [];
  const params = new URLSearchParams({ q: query.trim(), limit: '50' });
  if (caseId) params.set('case_id', caseId);
  return apiJson(`/api/v1/search?${params}`);
}
export async function verifyIntegrity() { return apiJson('/api/v1/integrity/verify'); }
export async function listIntegrityAnchors() { return apiJson('/api/v1/integrity/anchors'); }
export async function createIntegrityAnchor() { return apiJson('/api/v1/integrity/anchors', { method: 'POST' }); }
export async function verifyIntegrityAnchor(anchorId) { return apiJson(`/api/v1/integrity/anchors/${anchorId}/verify`); }

export async function listProfiles() { return apiJson('/api/v1/users'); }
export async function adminUpdateProfile(userId, role, clearanceLevel, isActive, department) {
  return apiJson(`/api/v1/users/${userId}`, {
    method: 'PATCH', body: JSON.stringify({ role, clearance_level: clearanceLevel, department: department || null, is_active: isActive }),
  });
}

export async function adminListCases() { return apiJson('/api/v1/admin/cases'); }
export async function adminCreateCase(payload) {
  return apiJson('/api/v1/admin/cases', { method: 'POST', body: JSON.stringify(payload) });
}
export async function adminReplaceCaseAssignments(caseId, payload) {
  return apiJson(`/api/v1/admin/cases/${caseId}/assignments`, { method: 'PATCH', body: JSON.stringify(payload) });
}

export async function listTimelineStatements(caseId) { return apiJson(`/api/v1/cases/${caseId}/timeline/statements`); }
export async function addTimelineStatement(caseId, payload) {
  return apiJson(`/api/v1/cases/${caseId}/timeline/statements`, { method: 'POST', body: JSON.stringify(payload) });
}
export async function listTimelineConflicts(caseId) { return apiJson(`/api/v1/cases/${caseId}/timeline/conflicts`); }
export async function setTimelineTravelMinutes(caseId, payload) {
  return apiJson(`/api/v1/cases/${caseId}/timeline/travel-times`, { method: 'POST', body: JSON.stringify(payload) });
}
export async function generateTimelineSuggestions(caseId) {
  return apiJson(`/api/v1/cases/${caseId}/timeline/suggestions/generate`, { method: 'POST' });
}
export async function confirmTimelineSuggestion(caseId, statementId) {
  return apiJson(`/api/v1/cases/${caseId}/timeline/statements/${statementId}/confirm`, { method: 'POST' });
}
export async function rejectTimelineSuggestion(caseId, statementId) {
  return apiJson(`/api/v1/cases/${caseId}/timeline/statements/${statementId}`, { method: 'DELETE' });
}

export async function askCaseAssistant(caseId, question) {
  return apiJson(`/api/v1/cases/${caseId}/assistant/ask`, { method: 'POST', body: JSON.stringify({ question }) });
}
export async function getCaseSummary(caseId) {
  return apiJson(`/api/v1/cases/${caseId}/assistant/summary`, { method: 'POST' });
}
export async function getLegalSectionSuggestions(caseId) {
  return apiJson(`/api/v1/cases/${caseId}/assistant/legal-sections`, { method: 'POST' });
}
export async function getCaseGaps(caseId) {
  return apiJson(`/api/v1/cases/${caseId}/assistant/gaps`);
}

export async function generateCertificate(documentId, versionId, expertForm) {
  const response = await apiFetchRaw(
    `/api/v1/documents/${documentId}/versions/${versionId}/certificate`,
    {
      method: 'POST',
      body: JSON.stringify({
        expert_name: expertForm.expertName,
        expert_designation: expertForm.expertDesignation,
        expert_qualification: expertForm.expertQualification,
        place: expertForm.place,
      }),
    },
  );
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = window.document.createElement('a');
  anchor.href = url;
  anchor.download = `section63-certificate-${documentId.slice(0, 8)}.pdf`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function getNoticeTypes(caseId) {
  return apiJson(`/api/v1/cases/${caseId}/notices/types`);
}

export async function generateNotice(caseId, payload) {
  const response = await apiFetchRaw(`/api/v1/cases/${caseId}/notices`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = window.document.createElement('a');
  anchor.href = url;
  anchor.download = `${payload.notice_type.toLowerCase()}-${caseId.slice(0, 8)}.pdf`;
  anchor.click();
  URL.revokeObjectURL(url);
}