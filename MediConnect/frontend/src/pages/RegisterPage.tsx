import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { ApiError } from "../lib/api";
import type { Me, UserRole } from "../lib/types";
import { useAuth } from "../auth/AuthContext";

export function RegisterPage() {
  const { refreshMe } = useAuth();
  const nav = useNavigate();

  const [role, setRole] = useState<UserRole>("patient");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api<Me>("/auth/register", {
        method: "POST",
        json: { role, display_name: displayName, email, password },
      });
      await refreshMe(); // in case backend auto-logs in later; safe no-op now
      nav("/login");
    } catch (e) {
      const err = e as ApiError;
      setError(err.message || "Registration failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card">
      <h2>Register</h2>
      <form onSubmit={onSubmit} className="form">
        <label>
          <div className="label">Role</div>
          <select value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
            <option value="patient">patient</option>
            <option value="doctor">doctor</option>
            <option value="org_admin">org_admin</option>
            <option value="platform_admin">platform_admin</option>
          </select>
        </label>
        <label>
          <div className="label">Display name</div>
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
        </label>
        <label>
          <div className="label">Email</div>
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
        </label>
        <label>
          <div className="label">Password</div>
          <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" minLength={6} required />
        </label>
        {error && <div className="error">{error}</div>}
        <button className="btn primary" disabled={submitting}>
          {submitting ? "Creating..." : "Create account"}
        </button>
      </form>
      <div className="muted" style={{ marginTop: 10 }}>
        Already have an account? <Link to="/login">Login</Link>
      </div>
    </div>
  );
}

