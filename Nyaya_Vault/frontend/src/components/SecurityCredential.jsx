import { ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import Badge, { clearanceTone, departmentTone } from "./Badge";

export default function SecurityCredential({ profile }) {
  const { t } = useTranslation(["securityCredential", "common"]);
  return (
    <section className="security-credential" aria-label={t("authorizationCredential")} data-guide="credential">
      <div className="eyebrow"><ShieldCheck size={15} /> {t("authorizationCredential")}</div>
      <strong>{profile?.role?.replaceAll("_", " ") || t("defaultRole", { ns: "common" })}</strong>
      <div className="credential-labels">
        <Badge tone={clearanceTone(profile?.clearance_level)}>{profile?.clearance_level || t("defaultClearance", { ns: "common" })}</Badge>
        {profile?.department ? <Badge tone={departmentTone(profile.department)}>{profile.department}</Badge> : null}
      </div>
      <span className="small muted">{t("accessNote")}</span>
    </section>
  );
}
