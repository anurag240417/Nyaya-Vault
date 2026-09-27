import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, Languages } from "lucide-react";
import { SUPPORTED_LANGUAGES } from "../i18n";

export default function LanguageSwitcher() {
  const { t, i18n } = useTranslation("topbar");
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const current =
    SUPPORTED_LANGUAGES.find((entry) => entry.code === i18n.resolvedLanguage) ||
    SUPPORTED_LANGUAGES[0];

  useEffect(() => {
    if (!open) return;
    function onDocClick(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) setOpen(false);
    }
    function onKey(event) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function choose(code) {
    i18n.changeLanguage(code);
    setOpen(false);
  }

  return (
    <div className="language-switcher" ref={rootRef}>
      <button
        type="button"
        className="language-trigger"
        data-guide="language"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={t("selectLanguage")}
        title={t("language")}
      >
        <Languages size={17} />
        <span className="hide-mobile">{current.nativeLabel}</span>
      </button>
      {open ? (
        <ul className="language-menu" role="listbox" aria-label={t("selectLanguage")}>
          {SUPPORTED_LANGUAGES.map((entry) => (
            <li key={entry.code}>
              <button
                type="button"
                role="option"
                aria-selected={entry.code === current.code}
                className={`language-option ${entry.code === current.code ? "selected" : ""}`}
                onClick={() => choose(entry.code)}
              >
                <span className="language-option-label">
                  <span>{entry.nativeLabel}</span>
                  <small>{entry.label}</small>
                </span>
                {entry.code === current.code ? <Check size={15} /> : null}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
