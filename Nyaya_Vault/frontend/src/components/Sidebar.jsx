import {
  BriefcaseBusiness,
  LayoutDashboard,
  Search,
  ShieldCheck,
  UserCog,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import SecurityCredential from "./SecurityCredential";
import { useAuth } from "../context/AuthContext";
export default function Sidebar() {
  const { t } = useTranslation("sidebar");
  const { profile } = useAuth();
  const links = [
    ["/dashboard", t("dashboard"), LayoutDashboard],
    ["/cases", t("cases"), BriefcaseBusiness],
    ["/search", t("search"), Search],
    ["/integrity", t("integrity"), ShieldCheck],
  ];
  return (
    <aside className="sidebar">
      <p className="eyebrow rail-heading">{t("workspaceIndex")}</p>
      <nav aria-label="Main navigation">
        {links.map(([to, label, icon]) => {
          const Icon = icon;
          return (
            <NavLink
              key={to}
              to={to}
              data-guide={`nav${to.replace("/", "-")}`}
              className={({ isActive }) =>
                `side-link ${isActive ? "active" : ""}`
              }
            >
              <span className="side-link-icon">
                <Icon size={18} />
              </span>
              <span>{label}</span>
            </NavLink>
          );
        })}
        {profile?.role === "ADMIN" ? (
          <NavLink
            to="/admin"
            data-guide="nav-admin"
            className={({ isActive }) =>
              `side-link ${isActive ? "active" : ""}`
            }
          >
            <span className="side-link-icon">
              <UserCog size={18} />
            </span>
            <span>{t("administration")}</span>
          </NavLink>
        ) : null}
      </nav>
      <div className="sidebar-footer">
        <SecurityCredential profile={profile} />
      </div>
    </aside>
  );
}
