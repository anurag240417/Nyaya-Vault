import { NavLink } from "react-router-dom";
export default function DossierTabs({ caseId, counts = {} }) {
  const tabs = [
    ["", "Case Summary"],
    ["documents", "Evidence Register", counts.documents],
    ["collaborators", "Access & Personnel", counts.collaborators],
    ["timeline", "Timeline & Conflicts", counts.timeline],
    ["assistant", "Case Assistant"],
    ["audit", "Audit Ledger", counts.audit],
  ];
  return (
    <nav aria-label="Case dossier sections" className="dossier-tabs">
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
