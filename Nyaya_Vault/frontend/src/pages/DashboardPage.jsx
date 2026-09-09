import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  BriefcaseBusiness,
  FileText,
  Search,
  ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";
import { getRecentActivity, listCases } from "../lib/api";
import { formatDate } from "../lib/format";
import LoadingState from "../components/LoadingState";
import Badge from "../components/Badge";
import { useAuth } from "../context/AuthContext";
import { useRefreshOnFocus } from "../hooks/useRefreshOnFocus";
export default function DashboardPage() {
  const { profile } = useAuth();
  const [cases, setCases] = useState([]),
    [activity, setActivity] = useState([]),
    [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    const [c, a] = await Promise.all([listCases(), getRecentActivity(10)]);
    setCases(c);
    setActivity(a);
  }, []);
  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, [reload]);
  useRefreshOnFocus(reload);
  if (loading) return <LoadingState label="Loading dashboard…" />;
  return (
    <div className="page">
      <section className="welcome-panel">
        <div>
          <p className="eyebrow">SECURE WORKSPACE</p>
          <h1>Good to see you, {profile?.username || "investigator"}.</h1>
          <p>
            Work appears only when your role, case assignment, and evidence
            clearance allow it.
          </p>
        </div>
        <Link className="button button-primary" to="/cases">
          Open cases <ArrowRight size={16} />
        </Link>
      </section>
      <div className="stat-grid">
        <div className="stat-card">
          <BriefcaseBusiness size={20} />
          <div>
            <strong>{cases.length}</strong>
            <span>accessible cases</span>
          </div>
        </div>
        <div className="stat-card">
          <ShieldCheck size={20} />
          <div>
            <strong>{profile?.clearance_level || "PUBLIC"}</strong>
            <span>clearance</span>
          </div>
        </div>
        <Link className="stat-card link-card" to="/search">
          <Search size={20} />
          <div>
            <strong>Evidence search</strong>
            <span>ACL-filtered full text</span>
          </div>
        </Link>
      </div>
      <div className="two-column">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Recent cases</h2>
              <p>Repository-style workspaces</p>
            </div>
            <Link to="/cases">View all</Link>
          </div>
          <div className="list-group">
            {cases.slice(0, 6).map((item) => (
              <Link className="list-row" key={item.id} to={`/cases/${item.id}`}>
                <BriefcaseBusiness size={17} />
                <div className="list-main">
                  <strong>{item.case_number}</strong>
                  <span>{item.title}</span>
                </div>
                <span className="muted small">
                  {formatDate(item.created_at)}
                </span>
              </Link>
            ))}
            {!cases.length ? (
              <div className="panel-empty">No cases assigned yet.</div>
            ) : null}
          </div>
        </section>
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Recent activity</h2>
              <p>Immutable events you may see</p>
            </div>
          </div>
          <div className="activity-list">
            {activity.map((entry) => (
              <div className="activity-item" key={entry.sequence}>
                <span className="activity-dot" />
                <div>
                  <div>
                    <strong>{entry.actor_username || "system"}</strong>{" "}
                    {entry.action.replaceAll("_", " ").toLowerCase()}
                  </div>
                  <div className="muted small">
                    {entry.case_number || "global"} ·{" "}
                    {formatDate(entry.timestamp)}
                  </div>
                </div>
                <Badge tone={entry.result === "SUCCESS" ? "success" : "danger"}>
                  {entry.result}
                </Badge>
              </div>
            ))}
            {!activity.length ? (
              <div className="panel-empty">
                <FileText size={18} /> No activity yet.
              </div>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  );
}
