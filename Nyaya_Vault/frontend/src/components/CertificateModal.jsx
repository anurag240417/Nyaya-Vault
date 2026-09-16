import { useState } from "react";
import Modal from "./Modal";
import { generateCertificate } from "../lib/api";

export default function CertificateModal({ documentId, versionId, onClose }) {
  const [form, setForm] = useState({
    expertName: "",
    expertDesignation: "",
    expertQualification: "",
    place: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await generateCertificate(documentId, versionId, form);
      onClose();
    } catch (err) {
      setError(err?.message || "Could not generate the certificate.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Generate Section 63 certificate"
      onClose={onClose}
      footer={
        <>
          <button className="button" onClick={onClose}>Cancel</button>
          <button form="cert-form" className="button button-primary" disabled={busy}>
            {busy ? "Generating…" : "Generate & download"}
          </button>
        </>
      }
    >
      <p className="muted small" >
        Part A (device operator) is filled automatically from this document's
        stored records. Part B requires a named expert who will sign the
        certificate before it is submitted to a court.
      </p>
      <form id="cert-form" className="form-stack" onSubmit={submit}>
        <label className="field">
          <span>Expert name</span>
          <input
            required
            value={form.expertName}
            onChange={(e) => setForm({ ...form, expertName: e.target.value })}
            placeholder="Dr. Ramesh Kumar"
          />
        </label>
        <label className="field">
          <span>Expert designation</span>
          <input
            required
            value={form.expertDesignation}
            onChange={(e) => setForm({ ...form, expertDesignation: e.target.value })}
            placeholder="Digital Forensic Examiner"
          />
        </label>
        <label className="field">
          <span>Expert qualification</span>
          <input
            required
            value={form.expertQualification}
            onChange={(e) => setForm({ ...form, expertQualification: e.target.value })}
            placeholder="M.Tech Cyber Security, CFCE"
          />
        </label>
        <label className="field">
          <span>Place</span>
          <input
            required
            value={form.place}
            onChange={(e) => setForm({ ...form, place: e.target.value })}
            placeholder="Gorakhpur"
          />
        </label>
        {error ? <p className="form-error" role="alert">{error}</p> : null}
      </form>
    </Modal>
  );
}