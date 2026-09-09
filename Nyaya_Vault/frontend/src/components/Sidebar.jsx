import {
  Activity,
  BriefcaseBusiness,
  LayoutDashboard,
  Search,
  ShieldCheck,
  Users,
  UserCog,
} from "lucide-react";
import { NavLink } from "react-router-dom";
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
      <nav>
        {links.map(([to, label, Icon]) => (
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
        ))}
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
        <div className="tiny-label">SIGNED IN AS</div>
        <div className="sidebar-role">
          <Users size={15} />
          <span>{profile?.role?.replaceAll("_", " ") || "USER"}</span>
        </div>
        <div className="sidebar-role">
          <Activity size={15} />
          <span>{profile?.clearance_level || "PUBLIC"} clearance</span>
        </div>
      </div>
    </aside>
  );
}
