import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  BriefcaseBusiness,
  FileText,
  Search,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getRecentActivity, listCases } from "../lib/api";
import { formatDate } from "../lib/format";
import LoadingState from "../components/LoadingState";
import SecurityCredential from "../components/SecurityCredential";
import Badge, { statusTone } from "../components/Badge";
import { useAuth } from "../context/AuthContext";
import { useRefreshOnFocus } from "../hooks/useRefreshOnFocus";
export default function DashboardPage() {
  const { t } = useTranslation("dashboard");
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
  if (loading) return <LoadingState label={t("loadingLabel")} />;
  return (
    <div className="page">
      <section className="duty-header">
        <div>
          <p className="eyebrow">{t("eyebrow")}</p>
          <h1>
            {t("greeting", {
              name: profile?.username || t("defaultInvestigator"),
            })}
          </h1>
          <p>{t("accessNote")}</p>
        </div>
        <Link className="button button-primary" to="/cases" data-guide="dash-open-cases">
          {t("actions.openCases")} <ArrowRight size={16} />
        </Link>
      </section>
      <div className="desk-context">
        <SecurityCredential profile={profile} />
        <div className="register-total" data-guide="dash-case-count"><strong>{cases.length}</strong><span>{t("stats.accessibleCaseRecords")}</span></div>
        <Link className="desk-search" to="/search" data-guide="dash-search"><Search size={22} /><div><strong>{t("search.title")}</strong><span>{t("search.description")}</span></div><ArrowRight size={18} /></Link>
      </div>
      <div className="desk-registers">
        <section className="panel">
          <div className="panel-header" data-guide="dash-case-register">
            <div>
              <h2>{t("caseRegister.title")}</h2>
              <p>{t("caseRegister.subtitle")}</p>
            </div>
            <Link to="/cases">{t("caseRegister.viewAll")}</Link>
          </div>
          <div className="list-group">
            {cases.slice(0, 6).map((item) => (
              <Link className="list-row" key={item.id} to={`/cases/${item.id}`}>
                <BriefcaseBusiness size={17} />
                <div className="list-main">
                  <strong>{item.case_number}</strong>
                  <span>{item.title}</span>
                </div>
                <Badge tone={statusTone(item.status)} data-guide="case-status">{(item.status || "UNDER_INVESTIGATION").replaceAll("_", " ")}</Badge>
                <span className="muted small">
                  {formatDate(item.created_at)}
                </span>
              </Link>
            ))}
            {!cases.length ? (
              <div className="panel-empty">{t("caseRegister.empty")}</div>
            ) : null}
          </div>
        </section>
        <section className="panel">
          <div className="panel-header" data-guide="dash-activity">
            <div>
              <h2>{t("activity.title")}</h2>
              <p>{t("activity.subtitle")}</p>
            </div>
          </div>
          <div className="activity-list">
            {activity.map((entry) => (
              <div className="activity-item" key={entry.sequence}>
                <code className="ledger-sequence">{entry.sequence}</code>
                <div>
                  <div>
                    <strong>{entry.actor_username || t("activity.systemActor")}</strong>{" "}
                    {entry.action.replaceAll("_", " ").toLowerCase()}
                  </div>
                  <div className="muted small">
                    {entry.case_number || t("activity.global")} ·{" "}
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
                <FileText size={18} /> {t("activity.empty")}
              </div>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  );
}
