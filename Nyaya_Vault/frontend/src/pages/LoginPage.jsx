import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { LockKeyhole, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/AuthContext";
export default function LoginPage() {
  const { t } = useTranslation("login");
  const { user, signIn, signUp } = useAuth();
  const [mode, setMode] = useState("signin"),
    [email, setEmail] = useState(""),
    [username, setUsername] = useState(""),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  const location = useLocation();
  useEffect(() => {
    setError("");
    setMessage("");
  }, [mode]);
  if (user)
    return <Navigate to={location.state?.from || "/dashboard"} replace />;
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (mode === "signin") await signIn(email, password);
      else {
        const result = await signUp(email, password, username);
        if (!result.session)
          setMessage(t("signUpSuccess"));
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-page">
      <div className="auth-hero">
        <div className="auth-logo">
          <ShieldCheck size={28} />
        </div>
        <p className="eyebrow">{t("eyebrowBrand")}</p>
        <h1>{t("brandName")}</h1>
        <p>
          {t("tagline")}
        </p>
        <div className="auth-feature">
          <LockKeyhole size={18} />
          <span>
            {t("feature")}
          </span>
        </div>
      </div>
      <form className="auth-card" onSubmit={submit}>
        <p className="eyebrow">{t("authorizedAccess")}</p>
        <h2>
          {mode === "signin" ? t("signInTitle") : t("signUpTitle")}
        </h2>
        <p className="muted">
          {t("newUserNote")}
        </p>
        {mode === "signup" ? (
          <label className="field">
            <span>{t("username")}</span>
            <input
              required
              autoComplete="username" value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={t("usernamePlaceholder")}
            />
          </label>
        ) : null}
        <label className="field">
          <span>{t("email")}</span>
          <input
            required
            type="email" autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("emailPlaceholder")}
          />
        </label>
        <label className="field">
          <span>{t("password")}</span>
          <input
            required
            minLength={8}
            type="password" autoComplete={mode === "signin" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
          />
        </label>
        {error ? <div role="alert" className="form-error">{error}</div> : null}
        {message ? <div role="status" className="form-success">{message}</div> : null}
        <button className="button button-primary button-block" disabled={busy}>
          {busy
            ? t("pleaseWait")
            : mode === "signin"
              ? t("signIn")
              : t("createAccount")}
        </button>
        <button
          type="button"
          className="button button-link button-block"
          onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
        >
          {mode === "signin"
            ? t("needAccount")
            : t("haveAccount")}
        </button>
      </form>
    </div>
  );
}
