/**
 * Small shared presentational pieces.
 *
 * Kept dependency-free and stateless so pages can compose them. Anything that
 * appears on more than one screen (the header, state badges, the spinner) lives
 * here to stay DRY.
 */
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";
import { SwimStatus } from "../lib/contract";
import type { SwimStatus as SwimStatusT } from "../lib/contract";

export function AppHeader() {
  const { user, logout } = useAuth();
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <Link to="/" className="brand">
          <span className="brand-mark">
            Swim<span>Lap</span>
          </span>
          <span className="brand-sub">Coordinator</span>
        </Link>
        <div className="header-spacer" />
        <Link to="/accounts" className="btn btn-ghost btn-sm">Accounts</Link>
        {user && (
          <div className="header-user">
            <span>
              {user.display_name} · <span className="muted">{user.username}</span>
            </span>
            <button className="btn btn-ghost btn-sm" onClick={logout}>
              Sign out
            </button>
          </div>
        )}
      </div>
      <div className="lane-rope" />
    </header>
  );
}

const STATE_LABEL: Record<SwimStatusT, string> = {
  [SwimStatus.Scheduled]: "Scheduled",
  [SwimStatus.Live]: "Live",
  [SwimStatus.Closed]: "Closed",
};

export function SwimBadge({ state }: { state: SwimStatusT }) {
  return (
    <span className={`badge badge-${state}`}>
      <span className="badge-dot" />
      {STATE_LABEL[state] ?? state}
    </span>
  );
}

export function Spinner() {
  return <span className="spin" aria-label="Loading" role="status" />;
}

export function Notice({ kind, children }: { kind: "error" | "info" | "warn"; children: ReactNode }) {
  return <div className={`notice notice-${kind}`}>{children}</div>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}
