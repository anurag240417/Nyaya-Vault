import { AlertCircle, CheckCircle2, X } from "lucide-react";
import { useTranslation } from "react-i18next";
export default function Toast({ toast, onClose }) {
  const { t } = useTranslation("common");
  if (!toast) return null;
  const ok = toast.type !== "error";
  return (
    <div role={ok ? "status" : "alert"} className={`toast ${ok ? "toast-success" : "toast-error"}`}>
      {ok ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
      <span>{toast.message}</span>
      <button className="toast-close" aria-label={t("dismissNotification")} onClick={onClose}>
        <X size={14} />
      </button>
    </div>
  );
}
