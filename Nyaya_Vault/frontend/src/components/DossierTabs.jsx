import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
export default function DossierTabs({ caseId, counts = {} }) {
  const { t } = useTranslation("common");
  const tabs = [
    ["", t("dossierTabs.summary")],
    ["documents", t("dossierTabs.documents"), counts.documents],
    ["collaborators", t("dossierTabs.collaborators"), counts.collaborators],
    ["timeline", t("dossierTabs.timeline"), counts.timeline],
    ["assistant", t("dossierTabs.assistant")],
    ["audit", t("dossierTabs.audit"), counts.audit],
  ];
  return (
    <nav aria-label={t("dossierTabs.sectionsLabel")} className="dossier-tabs">
      {tabs.map(([path, label, count]) => (
        <NavLink
          key={label}
          end={path === ""}
          to={`/cases/${caseId}/${path}`}
          className={({ isActive }) => `dossier-tab ${isActive ? "active" : ""}`}
        >
          <span>{label}</span>
          {Number.isFinite(count) ? (
            <span className="counter">{count}</span>
          ) : null}
        </NavLink>
      ))}
    </nav>
  );
}
