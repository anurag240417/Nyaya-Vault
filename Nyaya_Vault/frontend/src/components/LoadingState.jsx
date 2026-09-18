import Lottie from "lottie-react";
import { useTranslation } from "react-i18next";
import loaderAnimation from "../assets/loader.json";

export default function LoadingState({ fullPage = false, label }) {
  const { t } = useTranslation("common");
  return <div className={`loading-state ${fullPage ? "full-page" : ""}`} role="status">
    <div className="loading-animation" aria-hidden="true">
      <Lottie animationData={loaderAnimation} loop autoplay />
    </div>
    <span>{label ?? t("actions.loading")}</span>
  </div>;
}
