import { useCallback, useEffect, useMemo, useState } from "react";
import { BriefcaseBusiness, Plus, RefreshCw, Search } from "lucide-react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { createCase, listCases } from "../lib/api";
import { formatDate } from "../lib/format";
import { useAuth } from "../context/AuthContext";
import Modal from "../components/Modal";
import Badge, { statusTone } from "../components/Badge";
import EmptyState from "../components/EmptyState";
import LoadingState from "../components/LoadingState";
import Toast from "../components/Toast";
import ExpandableDescription from "../components/ExpandableDescription";
import { useRefreshOnFocus } from "../hooks/useRefreshOnFocus";
export default function CasesPage() {
  const { t } = useTranslation("cases");
  const { user, profile } = useAuth();
  const [cases, setCases] = useState([]),
    [query, setQuery] = useState(""),
    [loading, setLoading] = useState(true),
    [open, setOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [toast, setToast] = useState(null),
    [form, setForm] = useState({ case_number: "", title: "", description: "" });
  const canCreate = ["ADMIN", "INVESTIGATING_OFFICER"].includes(profile?.role);
  const reload = useCallback(async () => {
    setCases(await listCases());
  }, []);
  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, [reload]);
  useRefreshOnFocus(reload);
  const filtered = useMemo(
    () =>
      cases.filter((i) =>
        `${i.case_number} ${i.title} ${i.description || ""}`
          .toLowerCase()
          .includes(query.toLowerCase()),
      ),
    [cases, query],
  );
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await createCase(form, user.id);
      setForm({ case_number: "", title: "", description: "" });
      setOpen(false);
      await reload();
      setToast({ message: t("toast.created") });
    } catch (err) {
      setToast({ type: "error", message: err.message });
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page">
      <div className="page-title-row">
        <div>
          <p className="eyebrow">{t("eyebrow")}</p><h1>{t("title")}</h1>
          <p>{t("subtitle")}</p>
        </div>
        {canCreate ? (
          <button
            className="button button-primary"
            onClick={() => setOpen(true)}
          >
            <Plus size={16} /> {t("actions.newCase")}
          </button>
        ) : null}
      </div>
      <div className="toolbar">
        <div className="search-input">
          <Search size={16} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label={t("filterAria")} placeholder={t("searchPlaceholder")}
          />
        </div>
        <button
          className="button button-sm"
          type="button"
          onClick={() =>
            reload().catch((err) =>
              setToast({ type: "error", message: err.message }),
            )
          }
        >
          <RefreshCw size={14} /> {t("actions.refresh")}
        </button>
      </div>
      {loading ? (
        <LoadingState />
      ) : filtered.length ? (
        <div className="case-registry">
          {filtered.map((item) => (
            <article className="registry-entry" key={item.id}>
              <div className="registry-locator">
                <BriefcaseBusiness size={18} />
                <strong><Link to={`/cases/${item.id}`}>{item.case_number}</Link></strong>
                <span className="visibility-pill">{t("visibilityPrivate")}</span>
                <Badge tone={statusTone(item.status)}>
                  {(item.status || "UNDER_INVESTIGATION").replaceAll("_", " ")}
                </Badge>
              </div>
              <h3><Link to={`/cases/${item.id}`}>{item.title}</Link></h3>
              <ExpandableDescription>
                {item.description || t("noDescription")}
              </ExpandableDescription>
              <div className="case-meta">
                {t("createdOn", { date: formatDate(item.created_at) })}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<BriefcaseBusiness size={28} />}
          title={t("empty.title")}
          description={
            query
              ? t("empty.tryAnotherSearch")
              : t("empty.noAccessibleCases")
          }
          action={
            canCreate && !query ? (
              <button className="button" onClick={() => setOpen(true)}>
                {t("actions.createFirstCase")}
              </button>
            ) : null
          }
        />
      )}{" "}
      {open ? (
        <Modal
          title={t("modal.title")}
          onClose={() => setOpen(false)}
          footer={
            <>
              <button className="button" onClick={() => setOpen(false)}>
                {t("actions.cancel")}
              </button>
              <button
                form="create-case"
                className="button button-primary"
                disabled={busy}
              >
                {busy ? t("actions.creating") : t("actions.createCase")}
              </button>
            </>
          }
        >
          <form id="create-case" className="form-stack" onSubmit={submit}>
            <label className="field">
              <span>{t("form.caseNumber")}</span>
              <input
                required
                value={form.case_number}
                onChange={(e) =>
                  setForm({ ...form, case_number: e.target.value })
                }
                placeholder={t("form.caseNumberPlaceholder")}
              />
            </label>
            <label className="field">
              <span>{t("form.title")}</span>
              <input
                required
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </label>
            <label className="field">
              <span>{t("form.description")}</span>
              <textarea
                rows="5"
                maxLength="2000"
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
              />
            </label>
          </form>
        </Modal>
      ) : null}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
