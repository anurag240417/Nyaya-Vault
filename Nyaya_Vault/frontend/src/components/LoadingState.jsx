export default function LoadingState({ fullPage = false, label = "Loading…" }) {
  return <div className={`loading-state ${fullPage ? "full-page" : ""}`} role="status">
    <span className="spinner" aria-hidden="true" /><span>{label}</span>
  </div>;
}
