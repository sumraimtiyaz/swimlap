/**
 * Coordinator sign-in.
 *
 * The only unauthenticated screen. On success `useAuth` stores the session and
 * the router redirects to the dashboard. Timer accounts are refused here (they
 * belong on the mobile app) — the refusal message says exactly that.
 */
import { useState, type FormEvent } from "react";

import { useAuth } from "../hooks/useAuth";
import { Notice, Spinner } from "../components/ui";

export function LoginPage() {
  const { login, loading, error } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await login(username.trim(), password);
    } catch {
      // Error is surfaced via the `error` field from useAuth.
    }
  };

  const canSubmit = username.trim().length > 0 && password.length > 0 && !loading;

  return (
    <div className="auth-screen">
      <div className="auth-card card card-pad">
        <div className="auth-brand">
          <div className="brand-mark">
            Swim<span style={{ color: "var(--water)" }}>Lap</span>
          </div>
          <div className="brand-sub">Coordinator console</div>
        </div>

        <form onSubmit={submit} noValidate>
          <div className="field">
            <label htmlFor="username">Login id</label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="coordinator"
              autoFocus
            />
          </div>

          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div style={{ marginBottom: 14 }}>
              <Notice kind="error">{error}</Notice>
            </div>
          )}

          <button type="submit" className="btn btn-primary" style={{ width: "100%" }} disabled={!canSubmit}>
            {loading ? <Spinner /> : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
