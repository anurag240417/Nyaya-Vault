import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { LockKeyhole, ShieldCheck } from "lucide-react";
import { useAuth } from "../context/AuthContext";
export default function LoginPage() {
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
          setMessage("Account created. Confirm your email, then sign in.");
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
        <h1>Nyaya Vault</h1>
        <p>
          Secure case-scoped evidence management with immutable activity
          history.
        </p>
        <div className="auth-feature">
          <LockKeyhole size={18} />
          <span>
            Supabase Auth + FastAPI authorization + private Supabase storage
          </span>
        </div>
      </div>
      <form className="auth-card" onSubmit={submit}>
        <h2>
          {mode === "signin" ? "Sign in to Nyaya Vault" : "Create an account"}
        </h2>
        <p className="muted">
          New users start as CLERK / PUBLIC until an administrator changes
          access.
        </p>
        {mode === "signup" ? (
          <label className="field">
            <span>Username</span>
            <input
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="aditya"
            />
          </label>
        ) : null}
        <label className="field">
          <span>Email</span>
          <input
            required
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />
        </label>
        <label className="field">
          <span>Password</span>
          <input
            required
            minLength={8}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
          />
        </label>
        {error ? <div className="form-error">{error}</div> : null}
        {message ? <div className="form-success">{message}</div> : null}
        <button className="button button-primary button-block" disabled={busy}>
          {busy
            ? "Please wait…"
            : mode === "signin"
              ? "Sign in"
              : "Create account"}
        </button>
        <button
          type="button"
          className="button button-link button-block"
          onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
        >
          {mode === "signin"
            ? "Need an account? Sign up"
            : "Already have an account? Sign in"}
        </button>
      </form>
    </div>
  );
}
