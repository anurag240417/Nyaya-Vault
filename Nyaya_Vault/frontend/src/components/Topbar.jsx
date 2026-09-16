import { LogOut, Search, ShieldCheck, UserRound } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Avatar from "./Avatar";
export default function Topbar() {
  const { profile, signOut } = useAuth();
  const nav = useNavigate();
  async function out() {
    await signOut();
    nav("/login");
  }
  return (
    <header className="topbar">
      <Link className="brand" to="/dashboard">
        <span className="brand-mark">
          <ShieldCheck size={22} />
        </span>
        <span className="brand-name"><strong>Nyaya Vault</strong><small>Case & Evidence System</small></span>
      </Link>
      <button className="global-search" aria-label="Search cases and evidence" onClick={() => nav("/search")}>
        <Search size={16} />
        <span>Search evidence, documents, cases…</span>
      </button>
      <div className="topbar-actions">
        <Link className="profile-chip" to="/profile">
          <Avatar name={profile?.username} size="sm" />
          <span className="identity-name">{profile?.username || "Account"}<small>{profile?.role?.replaceAll("_", " ")}</small></span>
          <UserRound size={14} className="hide-mobile" />
        </Link>
        <button
          className="icon-button topbar-icon"
          onClick={out}
          title="Sign out" aria-label="Sign out"
        >
          <LogOut size={18} />
        </button>
      </div>
    </header>
  );
}
