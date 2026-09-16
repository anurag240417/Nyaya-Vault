import { useCallback, useEffect, useMemo, useState } from "react";
import { BriefcaseBusiness, Plus, RefreshCw, Search } from "lucide-react";
import { Link } from "react-router-dom";
import { createCase, listCases } from "../lib/api";
import { formatDate } from "../lib/format";
import { useAuth } from "../context/AuthContext";
import Modal from "../components/Modal";
import Badge, { statusTone } from "../components/Badge";
import EmptyState from "../components/EmptyState";
import LoadingState from "../components/LoadingState";
import Toast from "../components/Toast";
import { useRefreshOnFocus } from "../hooks/useRefreshOnFocus";
export default function CasesPage() {
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
      setToast({ message: "Case created and creator auto-assigned." });
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
          <h1>Cases</h1>
          <p>Private repository-style workspaces with scoped collaborators.</p>
        </div>
        {canCreate ? (
          <button
            className="button button-primary"
            onClick={() => setOpen(true)}
          >
            <Plus size={16} /> New case
          </button>
        ) : null}
      </div>
      <div className="toolbar">
        <div className="search-input">
          <Search size={16} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Find a case…"
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
          <RefreshCw size={14} /> Refresh
        </button>
      </div>
      {loading ? (
        <LoadingState />
      ) : filtered.length ? (
        <div className="case-grid">
          {filtered.map((item) => (
            <Link to={`/cases/${item.id}`} className="case-card" key={item.id}>
              <div className="case-card-title">
                <BriefcaseBusiness size={18} />
                <strong>{item.case_number}</strong>
                <span className="visibility-pill">Private</span>
                <Badge tone={statusTone(item.status)}>
                  {(item.status || "UNDER_INVESTIGATION").replaceAll("_", " ")}
                </Badge>
              </div>
              <h3>{item.title}</h3>
              <p>{item.description || "No description has been added."}</p>
              <div className="case-meta">
                Created {formatDate(item.created_at)}
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<BriefcaseBusiness size={28} />}
          title="No cases found"
          description={
            query
              ? "Try another search."
              : "You do not have any accessible cases."
          }
          action={
            canCreate && !query ? (
              <button className="button" onClick={() => setOpen(true)}>
                Create the first case
              </button>
            ) : null
          }
        />
      )}{" "}
      {open ? (
        <Modal
          title="Create a new case"
          onClose={() => setOpen(false)}
          footer={
            <>
              <button className="button" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button
                form="create-case"
                className="button button-primary"
                disabled={busy}
              >
                {busy ? "Creating…" : "Create case"}
              </button>
            </>
          }
        >
          <form id="create-case" className="form-stack" onSubmit={submit}>
            <label className="field">
              <span>Case number</span>
              <input
                required
                value={form.case_number}
                onChange={(e) =>
                  setForm({ ...form, case_number: e.target.value })
                }
                placeholder="FIR-2026-00124"
              />
            </label>
            <label className="field">
              <span>Title</span>
              <input
                required
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </label>
            <label className="field">
              <span>Description</span>
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
