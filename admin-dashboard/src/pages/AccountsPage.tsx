/**
 * Accounts (PRD §4, §8.1). Create timer accounts — the system generates the
 * password and shows it **once** here; it can never be retrieved again. Reset
 * issues a new one (also shown once); deactivate blocks login while keeping the
 * account and its captures for past reports.
 */
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { AppHeader, Notice, Spinner } from "../components/ui";
import { UserRole } from "../lib/contract";
import type { IssuedAccount, User } from "../api/types";

export function AccountsPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [issued, setIssued] = useState<IssuedAccount | null>(null); // one-time password panel

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setUsers(await api.listUsers());
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load accounts.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <AppHeader />
      <main className="page">
        <Link to="/" className="back-link">← Dashboard</Link>
        <div className="page-head">
          <div>
            <div className="eyebrow">People</div>
            <h1>Accounts</h1>
          </div>
        </div>

        {issued && <OneTimePassword issued={issued} onDone={() => setIssued(null)} />}

        <div className="grid-2">
          <section className="stack">
            <div className="card card-pad">
              <div className="section-title">Enrolled accounts</div>
              {loading && <div className="row-gap"><Spinner /> <span className="muted">Loading…</span></div>}
              {error && <Notice kind="error">{error}</Notice>}
              {!loading && !error && (
                <div style={{ overflowX: "auto" }}>
                  <table className="log">
                    <thead>
                      <tr><th>Name</th><th>Login id</th><th>Role</th><th>Active</th><th>Created</th><th></th></tr>
                    </thead>
                    <tbody>
                      {users.map((u) => (
                        <UserRow key={u.id} user={u} onIssued={setIssued} onChanged={load} />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>

          <aside className="stack">
            <CreateTimerPanel onIssued={setIssued} onCreated={load} />
          </aside>
        </div>
      </main>
    </>
  );
}

function UserRow({ user, onIssued, onChanged }: {
  user: User;
  onIssued: (a: IssuedAccount) => void;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const isTimer = user.role === UserRole.Timer;

  const reset = async () => {
    setBusy(true);
    try {
      onIssued(await api.resetPassword(user.id));
    } finally {
      setBusy(false);
    }
  };
  const deactivate = async () => {
    setBusy(true);
    try {
      await api.deactivateUser(user.id);
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  return (
    <tr style={!user.is_active ? { opacity: 0.55 } : undefined}>
      <td>{user.display_name}</td>
      <td className="mono">{user.username}</td>
      <td>{user.role}</td>
      <td>{user.is_active ? "Yes" : "No"}</td>
      <td className="muted">{user.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}</td>
      <td>
        {isTimer && user.is_active && (
          <span className="row-gap">
            <button className="btn btn-ghost btn-sm" onClick={reset} disabled={busy}>Reset</button>
            <button className="btn btn-ghost btn-sm" onClick={deactivate} disabled={busy}>Deactivate</button>
          </span>
        )}
      </td>
    </tr>
  );
}

function OneTimePassword({ issued, onDone }: { issued: IssuedAccount; onDone: () => void }) {
  return (
    <div className="card card-pad" style={{ borderColor: "var(--water)", marginBottom: 16 }}>
      <div className="section-title">Password for {issued.user.display_name}</div>
      <Notice kind="warn">
        Shown once — copy it now and hand it over. It cannot be retrieved again.
      </Notice>
      <div className="mono" style={{ fontSize: 28, fontWeight: 700, letterSpacing: 2, margin: "12px 0" }}>
        {issued.password}
      </div>
      <div className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
        Login id: <span className="mono">{issued.user.username}</span>
      </div>
      <button className="btn btn-primary btn-sm" onClick={onDone}>Done — I&apos;ve saved it</button>
    </div>
  );
}

function CreateTimerPanel({ onIssued, onCreated }: {
  onIssued: (a: IssuedAccount) => void;
  onCreated: () => void;
}) {
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const issued = await api.createTimer({
        username: username.trim(),
        display_name: displayName.trim(),
        role: UserRole.Timer,
      });
      onIssued(issued);
      setUsername("");
      setDisplayName("");
      onCreated();
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Could not create account.");
    } finally {
      setBusy(false);
    }
  };

  const canSubmit = username.trim().length > 0 && displayName.trim().length > 0 && !busy;

  return (
    <div className="card card-pad">
      <div className="section-title">Enroll a timer</div>
      <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
        The system generates the password and shows it once.
      </p>
      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="t-name">Name</label>
          <input id="t-name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Jordan Pike" maxLength={120} />
        </div>
        <div className="field">
          <label htmlFor="t-user">Login id</label>
          <input id="t-user" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="jordan" autoCapitalize="none" />
        </div>
        {err && <div style={{ marginBottom: 12 }}><Notice kind="error">{err}</Notice></div>}
        <button type="submit" className="btn btn-primary" disabled={!canSubmit}>
          {busy ? <Spinner /> : "Create timer"}
        </button>
      </form>
    </div>
  );
}
