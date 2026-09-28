import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { LockKeyhole, LogIn } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/AuthContext";

// Shared demo accounts for evaluators (e.g. SIH judges). Set these in .env
// locally and in the hosting provider's environment; the card is hidden when
// they are missing. They are bundled into the public JS, so use demo-only
// accounts.
const DEMO_ACCOUNTS = [
  {
    key: "admin",
    email: import.meta.env.VITE_DEMO_ADMIN_EMAIL,
    password: import.meta.env.VITE_DEMO_ADMIN_PASSWORD,
  },
  {
    key: "officer",
    email: import.meta.env.VITE_DEMO_OFFICER_EMAIL,
    password: import.meta.env.VITE_DEMO_OFFICER_PASSWORD,
  },
].filter((account) => account.email && account.password);
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
  async function signInWithDemo(account) {
    setMode("signin");
    setEmail(account.email);
    setPassword(account.password);
    setBusy(true);
    setError("");
    try {
      await signIn(account.email, account.password);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
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
        <img className="auth-logo" src="/nyaya-vault-emblem.png" alt="" />
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
        {mode === "signin" && DEMO_ACCOUNTS.length ? (
          <>
            <section className="demo-access" data-guide="demo-accounts" aria-labelledby="demo-access-title">
              <p className="eyebrow" id="demo-access-title">{t("demo.title")}</p>
              <p className="demo-access-note">{t("demo.note")}</p>
              {DEMO_ACCOUNTS.map((account) => (
                <div className="demo-account" key={account.key}>
                  <div className="demo-account-head">
                    <strong>{t(`demo.roles.${account.key}`)}</strong>
                    <button
                      type="button"
                      className="button button-sm button-primary"
                      disabled={busy}
                      onClick={() => signInWithDemo(account)}
                    >
                      <LogIn size={14} /> {t("demo.signInAs")}
                    </button>
                  </div>
                  <dl>
                    <dt>{t("email")}</dt>
                    <dd><code>{account.email}</code></dd>
                    <dt>{t("password")}</dt>
                    <dd><code>{account.password}</code></dd>
                  </dl>
                </div>
              ))}
            </section>
            <p className="demo-divider"><span>{t("demo.orEmail")}</span></p>
          </>
        ) : null}
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
        <button className="button button-primary button-block" data-guide="login-submit" disabled={busy}>
          {busy
            ? t("pleaseWait")
            : mode === "signin"
              ? t("signIn")
              : t("createAccount")}
        </button>
        <button
          type="button"
          className="button button-link button-block"
          data-guide={mode === "signin" ? "login-toggle" : undefined}
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
