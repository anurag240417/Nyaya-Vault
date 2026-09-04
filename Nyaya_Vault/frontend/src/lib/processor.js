import { apiFetchRaw } from './api';

export const isProcessorConfigured = () => true;

export async function requestDocumentProcessing({ documentId, versionId }) {
  const response = await apiFetchRaw(`/api/v1/documents/${documentId}/process`, {
    method: 'POST',
    body: JSON.stringify({ version_id: versionId }),
  });
  return response.json();
}

export async function exportRedactedDocument({ documentId, filename = 'redacted-document.pdf' }) {
  const response = await apiFetchRaw(`/api/v1/documents/${documentId}/redacted-export`, { method: 'POST' });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = window.document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
