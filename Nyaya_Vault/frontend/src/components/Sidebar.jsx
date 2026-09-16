import {
  BriefcaseBusiness,
  LayoutDashboard,
  Search,
  ShieldCheck,
  UserCog,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import SecurityCredential from "./SecurityCredential";
import { useAuth } from "../context/AuthContext";
const links = [
  ["/dashboard", "Dashboard", LayoutDashboard],
  ["/cases", "Cases", BriefcaseBusiness],
  ["/search", "Search", Search],
  ["/integrity", "Integrity", ShieldCheck],
];
export default function Sidebar() {
  const { profile } = useAuth();
  return (
    <aside className="sidebar">
      <p className="eyebrow rail-heading">Workspace index</p>
      <nav aria-label="Main navigation">
        {links.map(([to, label, icon]) => {
          const Icon = icon;
          return (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `side-link ${isActive ? "active" : ""}`
              }
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          );
        })}
        {profile?.role === "ADMIN" ? (
          <NavLink
            to="/admin"
            className={({ isActive }) =>
              `side-link ${isActive ? "active" : ""}`
            }
          >
            <UserCog size={18} />
            <span>Administration</span>
          </NavLink>
        ) : null}
      </nav>
      <div className="sidebar-footer">
        <SecurityCredential profile={profile} />
      </div>
    </aside>
  );
}
