import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import Modal from "./Modal";
import { getNoticeTypes, generateNotice } from "../lib/api";

export default function NoticeModal({ caseId, onClose, setToast }) {
  const { t } = useTranslation(["notice", "common"]);
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
      setToast?.({ message: t("successMessage") });
      onClose();
    } catch (err) {
      setError(err?.message || t("defaultError"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={t("title")}
      onClose={onClose}
      footer={
        <>
          <button className="button" onClick={onClose}>{t("actions.cancel", { ns: "common" })}</button>
          <button form="notice-form" className="button button-primary" disabled={busy || !selectedKey}>
            {busy ? t("generating") : t("generateAndDownload")}
          </button>
        </>
      }
    >
      {!types ? (
        <p className="muted small">{t("loadingTypes")}</p>
      ) : (
        <form id="notice-form" className="form-stack" onSubmit={submit}>
          <label className="field" data-guide="notice-type">
            <span>{t("noticeType")}</span>
            <select value={selectedKey} onChange={(e) => { setSelectedKey(e.target.value); setFieldValues({}); }}>
              {types.map((nt) => <option key={nt.key} value={nt.key}>{nt.title}</option>)}
            </select>
          </label>
          {selectedType?.statute_reference ? (
            <p className="muted small" >{t("issuedUnder", { reference: selectedType.statute_reference })}</p>
          ) : null}

          <label className="field">
            <span>{t("recipientName")}</span>
            <input required value={recipientName} onChange={(e) => setRecipientName(e.target.value)} />
          </label>
          <label className="field">
            <span>{t("recipientAddress")}</span>
            <input required value={recipientAddress} onChange={(e) => setRecipientAddress(e.target.value)} />
          </label>

          {selectedType?.fields.map((f) => (
            <label className="field" key={f.key}>
              <span>{f.label}{f.required ? "" : t("optionalSuffix")}</span>
              <input
                required={f.required}
                value={fieldValues[f.key] || ""}
                onChange={(e) => setField(f.key, e.target.value)}
                placeholder={f.placeholder}
              />
            </label>
          ))}

          <label className="field">
            <span>{t("noticeText")}</span>
            <textarea
              required
              rows={6}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={t("noticeTextPlaceholder")}
            />
          </label>
          <label className="field">
            <span>{t("place")}</span>
            <input required value={place} onChange={(e) => setPlace(e.target.value)} placeholder={t("placePlaceholder")} />
          </label>

          {error ? <p className="form-error" role="alert">{error}</p> : null}
        </form>
      )}
    </Modal>
  );
}
