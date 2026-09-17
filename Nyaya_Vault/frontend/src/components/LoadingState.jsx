import Lottie from "lottie-react";
import loaderAnimation from "../assets/loader.json";

export default function LoadingState({ fullPage = false, label = "Loading…" }) {
  return <div className={`loading-state ${fullPage ? "full-page" : ""}`} role="status">
    <div className="loading-animation" aria-hidden="true">
      <Lottie animationData={loaderAnimation} loop autoplay />
    </div>
    <span>{label}</span>
  </div>;
}
