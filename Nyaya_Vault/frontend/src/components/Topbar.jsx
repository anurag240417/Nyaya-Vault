import { LogOut } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/AuthContext";
import Avatar from "./Avatar";
import LanguageSwitcher from "./LanguageSwitcher";
export default function Topbar() {
  const { t } = useTranslation("topbar");
  const { profile, signOut } = useAuth();
  const nav = useNavigate();
  async function out() {
    await signOut();
    nav("/login");
  }
  return (
    <header className="topbar">
      <Link className="brand" to="/dashboard" data-guide="brand">
        <img className="brand-logo" src="/nyaya-vault-emblem.png" alt="" />
        <span className="brand-name"><strong>Nyaya Vault</strong><small>{t("brandTagline")}</small></span>
      </Link>
      <div className="topbar-actions">
        <LanguageSwitcher />
        <Link className="profile-chip" to="/profile" data-guide="profile-chip">
          <Avatar name={profile?.username} size="sm" />
          <span className="identity-name">{profile?.username || t("account")}<small>{profile?.role?.replaceAll("_", " ")}</small></span>
        </Link>
        <button
          className="icon-button topbar-icon logout-button"
          data-guide="logout"
          onClick={out}
          title={t("signOut")} aria-label={t("signOut")}
        >
          <LogOut size={17} />
          <span className="hide-mobile">{t("logout")}</span>
        </button>
      </div>
    </header>
  );
}
