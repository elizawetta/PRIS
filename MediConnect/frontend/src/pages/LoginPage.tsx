import { useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import type { ApiError } from "../lib/api";
import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const { login, state } = useAuth();
  const nav = useNavigate();
  const loc = useLocation() as any;
  const redirectTo = useMemo(() => (loc.state?.from as string | undefined) || "/documents", [loc.state]);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username.trim(), password);
      nav(redirectTo, { replace: true });
    } catch (e) {
      const err = e as ApiError;
      setError(err.message || "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (state.status === "authenticated") {
    return (
      <div className="card">
        <h2>Already logged in</h2>
        <p className="muted">
          You are logged in as <b>{state.me.display_name}</b>.
        </p>
        <Link className="btn" to="/documents">
          Go to Documents
        </Link>
      </div>
    );
  }

  return (
    <div className="grid-2">
      <div className="card">
        <h2>Login</h2>
        <p className="muted">Use email (or provider subject) + password.</p>
        <form onSubmit={onSubmit} className="form">
          <label>
            <div className="label">Email</div>
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="email" required />
          </label>
          <label>
            <div className="label">Password</div>
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          {error && <div className="error">{error}</div>}
          <button className="btn primary" disabled={submitting}>
            {submitting ? "Logging in..." : "Login"}
          </button>
        </form>
        <div className="muted" style={{ marginTop: 10 }}>
          No account? <Link to="/register">Register</Link>
        </div>
      </div>
      <div className="card subtle">
        <h3>MediConnect MVP</h3>
        <ul className="list">
          <li>JWT auth</li>
          <li>Documents as strings</li>
          <li>Consents to user/org</li>
          <li>Audit trail</li>
        </ul>
      </div>
    </div>
  );
}

