import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
export default function NotFoundPage() {
  const { t } = useTranslation("notFound");
  return (
    <div className="not-found">
      <strong>{t("code")}</strong>
      <h1>{t("title")}</h1>
      <p>{t("description")}</p>
      <Link className="button button-primary" to="/dashboard">
        {t("backLink")}
      </Link>
    </div>
  );
}
