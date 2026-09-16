import { useEffect, useState } from "react";
import Modal from "./Modal";
import { getNoticeTypes, generateNotice } from "../lib/api";

export default function NoticeModal({ caseId, onClose, setToast }) {
  const [types, setTypes] = useState(null);
  const [selectedKey, setSelectedKey] = useState("");
  const [recipientName, setRecipientName] = useState("");
  const [recipientAddress, setRecipientAddress] = useState("");
  const [fieldValues, setFieldValues] = useState({});
  const [body, setBody] = useState("");
  const [place, setPlace] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getNoticeTypes(caseId)
      .then((list) => {
        setTypes(list);
        if (list.length) setSelectedKey(list[0].key);
      })
      .catch((e) => setError(e.message));
  }, [caseId]);

  const selectedType = types?.find((t) => t.key === selectedKey);

  function setField(key, value) {
    setFieldValues({ ...fieldValues, [key]: value });
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await generateNotice(caseId, {
        notice_type: selectedKey,
        recipient_name: recipientName,
        recipient_address: recipientAddress,
        fields: fieldValues,
        body,
        place,
      });
      setToast?.({ message: "Notice generated." });
      onClose();
    } catch (err) {
      setError(err?.message || "Could not generate the notice.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Generate legal notice"
      onClose={onClose}
      footer={
        <>
          <button className="button" onClick={onClose}>Cancel</button>
          <button form="notice-form" className="button button-primary" disabled={busy || !selectedKey}>
            {busy ? "Generating…" : "Generate & download"}
          </button>
        </>
      }
    >
      {!types ? (
        <p className="muted small">Loading notice types…</p>
      ) : (
        <form id="notice-form" className="form-stack" onSubmit={submit}>
          <label className="field">
            <span>Notice type</span>
            <select value={selectedKey} onChange={(e) => { setSelectedKey(e.target.value); setFieldValues({}); }}>
              {types.map((t) => <option key={t.key} value={t.key}>{t.title}</option>)}
            </select>
          </label>
          {selectedType?.statute_reference ? (
            <p className="muted small" style={{ margin: 0 }}>Issued under: {selectedType.statute_reference}</p>
          ) : null}

          <label className="field">
            <span>Recipient name</span>
            <input required value={recipientName} onChange={(e) => setRecipientName(e.target.value)} />
          </label>
          <label className="field">
            <span>Recipient address</span>
            <input required value={recipientAddress} onChange={(e) => setRecipientAddress(e.target.value)} />
          </label>

          {selectedType?.fields.map((f) => (
            <label className="field" key={f.key}>
              <span>{f.label}{f.required ? "" : " (optional)"}</span>
              <input
                required={f.required}
                value={fieldValues[f.key] || ""}
                onChange={(e) => setField(f.key, e.target.value)}
                placeholder={f.placeholder}
              />
            </label>
          ))}

          <label className="field">
            <span>Notice text (grounds, allegations, demand - your own wording)</span>
            <textarea
              required
              rows={6}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="State the facts, the demand, and the deadline for compliance…"
            />
          </label>
          <label className="field">
            <span>Place</span>
            <input required value={place} onChange={(e) => setPlace(e.target.value)} placeholder="Pune" />
          </label>

          {error ? <p style={{ color: "#b91c1c", fontSize: "0.85rem" }}>{error}</p> : null}
        </form>
      )}
    </Modal>
  );
}
