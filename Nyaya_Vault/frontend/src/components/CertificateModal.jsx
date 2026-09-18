import { useState } from "react";
import { useTranslation } from "react-i18next";
import Modal from "./Modal";
import { generateCertificate } from "../lib/api";

export default function CertificateModal({ documentId, versionId, onClose }) {
  const { t } = useTranslation(["certificate", "common"]);
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
          <button form="cert-form" className="button button-primary" disabled={busy}>
            {busy ? t("generating") : t("generateAndDownload")}
          </button>
        </>
      }
    >
      <p className="muted small" >
        {t("description")}
      </p>
      <form id="cert-form" className="form-stack" onSubmit={submit}>
        <label className="field">
          <span>{t("expertName")}</span>
          <input
            required
            value={form.expertName}
            onChange={(e) => setForm({ ...form, expertName: e.target.value })}
            placeholder={t("expertNamePlaceholder")}
          />
        </label>
        <label className="field">
          <span>{t("expertDesignation")}</span>
          <input
            required
            value={form.expertDesignation}
            onChange={(e) => setForm({ ...form, expertDesignation: e.target.value })}
            placeholder={t("expertDesignationPlaceholder")}
          />
        </label>
        <label className="field">
          <span>{t("expertQualification")}</span>
          <input
            required
            value={form.expertQualification}
            onChange={(e) => setForm({ ...form, expertQualification: e.target.value })}
            placeholder={t("expertQualificationPlaceholder")}
          />
        </label>
        <label className="field">
          <span>{t("place")}</span>
          <input
            required
            value={form.place}
            onChange={(e) => setForm({ ...form, place: e.target.value })}
            placeholder={t("placePlaceholder")}
          />
        </label>
        {error ? <p className="form-error" role="alert">{error}</p> : null}
      </form>
    </Modal>
  );
}