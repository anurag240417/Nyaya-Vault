import { Shield, UserRound } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/AuthContext";
import Avatar from "../components/Avatar";
import Badge, { clearanceTone } from "../components/Badge";
import { formatDate } from "../lib/format";
export default function ProfilePage() {
  const { t } = useTranslation("profile");
  const { user, profile } = useAuth();
  return (
    <div className="page">
      <div className="page-title-row">
        <div>
          <p className="eyebrow">{t("eyebrow")}</p><h1>{t("title")}</h1>
          <p>{t("subtitle")}</p>
        </div>
      </div>
      <section className="panel profile-panel">
        <div className="profile-hero">
          <Avatar name={profile?.username} size="lg" />
          <div>
            <h2>{profile?.username}</h2>
            <p>{user?.email}</p>
            <div className="button-row">
              <Badge tone="info">{profile?.role?.replaceAll("_", " ")}</Badge>
              <Badge tone={clearanceTone(profile?.clearance_level)}>
                {profile?.clearance_level}
              </Badge>
            </div>
          </div>
        </div>
        <dl className="definition-grid">
          <dt>
            <UserRound size={15} /> {t("userId")}
          </dt>
          <dd>
            <code>{user?.id}</code>
          </dd>
          <dt>
            <Shield size={15} /> {t("accountState")}
          </dt>
          <dd>{profile?.is_active ? t("active") : t("disabled")}</dd>
          <dt>{t("department")}</dt><dd>{profile?.department || t("unassigned")}</dd>
          <dt>{t("created")}</dt>
          <dd>{formatDate(profile?.created_at)}</dd>
        </dl>
      </section>
    </div>
  );
}
