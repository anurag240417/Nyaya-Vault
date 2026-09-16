import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  BriefcaseBusiness,
  FileText,
  Search,
} from "lucide-react";
import { Link } from "react-router-dom";
import { getRecentActivity, listCases } from "../lib/api";
import { formatDate } from "../lib/format";
import LoadingState from "../components/LoadingState";
import SecurityCredential from "../components/SecurityCredential";
import Badge, { statusTone } from "../components/Badge";
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
  if (loading) return <LoadingState label="Loading case desk…" />;
  return (
    <div className="page">
      <section className="duty-header">
        <div>
          <p className="eyebrow">CASE DESK</p>
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
      <div className="desk-context">
        <SecurityCredential profile={profile} />
        <div className="register-total"><strong>{cases.length}</strong><span>accessible case records</span></div>
        <Link className="desk-search" to="/search"><Search size={22} /><div><strong>Case & Evidence Search</strong><span>Search records and extracted evidence within your access.</span></div><ArrowRight size={18} /></Link>
      </div>
      <div className="two-column">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Assigned Case Register</h2>
              <p>Your accessible case records, most recent first</p>
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
                <Badge tone={statusTone(item.status)}>{(item.status || "UNDER_INVESTIGATION").replaceAll("_", " ")}</Badge>
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
              <h2>Recent Activity Ledger</h2>
              <p>Recorded actions within your access</p>
            </div>
          </div>
          <div className="activity-list">
            {activity.map((entry) => (
              <div className="activity-item" key={entry.sequence}>
                <code className="ledger-sequence">{entry.sequence}</code>
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
