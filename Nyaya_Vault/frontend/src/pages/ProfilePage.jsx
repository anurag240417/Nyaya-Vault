import { useEffect, useState } from "react";
import { KeyRound, Shield, UserRound } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/AuthContext";
import Avatar from "../components/Avatar";
import Badge, { clearanceTone } from "../components/Badge";
import { getMySigningKey } from "../lib/api";
import { formatDate } from "../lib/format";
export default function ProfilePage() {
  const { t } = useTranslation("profile");
  const { user, profile } = useAuth();
  const [signingKey, setSigningKey] = useState(null);
  const [signingKeyError, setSigningKeyError] = useState("");
  const [showKey, setShowKey] = useState(false);
  useEffect(() => {
    getMySigningKey().then(setSigningKey).catch((e) => setSigningKeyError(e.message));
  }, []);
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
          <dt>
            <KeyRound size={15} /> {t("signingKey.label")}
          </dt>
          <dd>
            {signingKey ? (
              <>
                <code data-guide="profile-signing-key">{signingKey.fingerprint}</code>{" "}
                <span className="muted small">({signingKey.algorithm})</span>
                <p className="muted small">{t("signingKey.description")}</p>
                <button className="button button-sm" data-guide="profile-show-key" onClick={() => setShowKey((v) => !v)}>
                  {showKey ? t("signingKey.hide") : t("signingKey.show")}
                </button>
                {showKey ? <pre className="wrap-code small">{signingKey.public_key_pem}</pre> : null}
              </>
            ) : signingKeyError ? (
              <span className="muted">{signingKeyError}</span>
            ) : (
              <span className="muted">{t("signingKey.loading")}</span>
            )}
          </dd>
        </dl>
      </section>
    </div>
  );
}
