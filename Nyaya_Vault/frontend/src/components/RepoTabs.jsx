import { NavLink } from "react-router-dom";
export default function RepoTabs({ caseId, counts = {} }) {
  const tabs = [
    ["", "Overview"],
    ["documents", "Documents", counts.documents],
    ["collaborators", "Collaborators", counts.collaborators],
    ["timeline", "Conflicts", counts.timeline],
    ["audit", "Audit trail", counts.audit],
  ];
  return (
    <nav className="repo-tabs">
      {tabs.map(([path, label, count]) => (
        <NavLink
          key={label}
          end={path === ""}
          to={`/cases/${caseId}/${path}`}
          className={({ isActive }) => `repo-tab ${isActive ? "active" : ""}`}
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
