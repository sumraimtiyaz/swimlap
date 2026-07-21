/**
 * Running a single swim: assign the timer, watch the report build live (per-lap
 * deviations vs. the simulated reference, plus the four summary numbers), and
 * close it. Every screen built on simulated data carries the banner (PRD §9).
 */
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { useLiveSwims, useSwimReport } from "../hooks/useSwims";
import { AppHeader, Notice, Spinner, SwimBadge } from "../components/ui";
import { fmtClockTime, fmtDeviation, fmtLapTime } from "../lib/format";
import { ClosureMethod, SwimStatus } from "../lib/contract";
import type { Report, SwimDetail, User } from "../api/types";

const CLOSURE_LABEL: Record<string, string> = {
  [ClosureMethod.TimerCompleted]: "timer marked completed",
  [ClosureMethod.AutoInactivity]: "auto-closed after inactivity",
  [ClosureMethod.Coordinator]: "closed by coordinator",
};

export function SwimDetailPage() {
  const params = useParams();
  const swimId = Number(params.swimId);

  const [swim, setSwim] = useState<SwimDetail | null>(null);
  const [timers, setTimers] = useState<User[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const [detail, keepers] = await Promise.all([api.getSwim(swimId, signal), api.listTimers(signal)]);
      setSwim(detail);
      setTimers(keepers);
      setLoadError(null);
    } catch (err) {
      if (signal?.aborted) return;
      setLoadError(err instanceof ApiError ? err.message : "Could not load this swim.");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [swimId]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const isClosed = swim?.status === SwimStatus.Closed;
  const { report, initialLoading } = useSwimReport(swimId, !isClosed);

  if (loading) {
    return (
      <>
        <AppHeader />
        <main className="page">
          <div className="card card-pad row-gap"><Spinner /> <span className="muted">Loading swim…</span></div>
        </main>
      </>
    );
  }

  if (loadError || !swim) {
    return (
      <>
        <AppHeader />
        <main className="page">
          <Link to="/" className="back-link">← All swims</Link>
          <Notice kind="error">{loadError ?? "Swim not found."}</Notice>
        </main>
      </>
    );
  }

  return (
    <>
      <AppHeader />
      <main className="page">
        <Link to="/" className="back-link">← All swims</Link>

        <div className="page-head">
          <div>
            <div className="row-gap" style={{ marginBottom: 6 }}>
              <SwimBadge state={swim.status} />
              {swim.status === SwimStatus.Closed && swim.closure_method && (
                <span className="muted" style={{ fontSize: 13 }}>
                  {CLOSURE_LABEL[swim.closure_method] ?? swim.closure_method}
                </span>
              )}
            </div>
            <h1>{swim.swimmer_name}</h1>
            <div className="heat-row-meta mono" style={{ marginTop: 4 }}>
              {swim.venue_name} · Lane {swim.lane_no} · {fmtClockTime(swim.scheduled_start)}
              {swim.lap_target != null ? ` · target ${swim.lap_target}` : ""}
            </div>
          </div>
          <LifecycleControls swim={swim} onChanged={() => load()} />
        </div>

        <div className="grid-2">
          <section className="stack">
            <ReportView report={report} loading={initialLoading} />
          </section>
          <aside className="stack">
            <LiveStatus swimId={swimId} />
            <AssignPanel swim={swim} timers={timers} onChanged={() => load()} />
          </aside>
        </div>
      </main>
    </>
  );
}

function LifecycleControls({ swim, onChanged }: { swim: SwimDetail; onChanged: () => void }) {
  const [busy, setBusy] = useState<null | "close" | "sim">(null);
  const [err, setErr] = useState<string | null>(null);

  const run = async (kind: "close" | "sim", fn: () => Promise<unknown>) => {
    setBusy(kind);
    setErr(null);
    try {
      await fn();
      onChanged();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Action failed.");
    } finally {
      setBusy(null);
    }
  };

  if (swim.status === SwimStatus.Closed) {
    return <span className="muted" style={{ fontSize: 13 }}>This swim is closed. There is no reopen.</span>;
  }

  return (
    <div style={{ textAlign: "right" }}>
      <div className="row-gap" style={{ justifyContent: "flex-end" }}>
        <button className="btn btn-ghost" disabled={busy !== null}
          title="Inject simulated taps (demo/QA — no phone needed)"
          onClick={() => run("sim", () => api.simulateSwim(swim.id))}>
          {busy === "sim" ? <Spinner /> : "Simulate laps"}
        </button>
        <button className="btn btn-danger" disabled={busy !== null}
          onClick={() => run("close", () => api.closeSwim(swim.id))}>
          {busy === "close" ? <Spinner /> : "Close swim"}
        </button>
      </div>
      {err && <div style={{ marginTop: 10, maxWidth: 320 }}><Notice kind="error">{err}</Notice></div>}
    </div>
  );
}

function LiveStatus({ swimId }: { swimId: number }) {
  const { rows } = useLiveSwims();
  const row = useMemo(() => rows.find((r) => r.swim_id === swimId), [rows, swimId]);
  if (!row) return null;
  return (
    <div className="card card-pad">
      <div className="section-title">Live status</div>
      <div className="row-between" style={{ padding: "4px 0" }}>
        <span className="muted">Connected</span>
        <span className={row.connected ? "flag flag-ok" : "flag flag-late"}>{row.connected ? "Yes" : "No"}</span>
      </div>
      <div className="row-between" style={{ padding: "4px 0" }}>
        <span className="muted">Laps captured</span>
        <span className="mono">{row.lap_count}</span>
      </div>
      <div className="row-between" style={{ padding: "4px 0" }}>
        <span className="muted">Tapping</span>
        {row.stalled ? <span className="flag flag-invalid">⚠ stalled</span> : <span className="muted">active</span>}
      </div>
    </div>
  );
}

function ReportView({ report, loading }: { report: Report | null; loading: boolean }) {
  if (loading && !report) {
    return <div className="card card-pad row-gap"><Spinner /> <span className="muted">Building report…</span></div>;
  }
  if (!report) return <div className="card card-pad"><span className="muted">No report yet.</span></div>;

  const s = report.summary;
  return (
    <>
      {report.simulated && (
        <div className="notice notice-warn" style={{ fontWeight: 700, letterSpacing: 0.5 }}>
          {report.banner}
        </div>
      )}

      <div className="card card-pad">
        <div className="section-title">Report</div>
        <div style={{ overflowX: "auto" }}>
          <table className="log">
            <thead>
              <tr>
                <th>Lap</th>
                <th>Recorded</th>
                <th>Cumulative</th>
                <th>Reference</th>
                <th>Deviation</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {report.laps.length === 0 && (
                <tr><td colSpan={6} className="muted">No captures yet.</td></tr>
              )}
              {report.laps.map((l) => (
                <tr key={l.seq} style={!l.is_valid ? { opacity: 0.6 } : undefined}>
                  <td className="mono">{l.lap_no}</td>
                  <td>{fmtLapTime(l.recorded_ms)}</td>
                  <td>{fmtLapTime(l.cumulative_ms)}</td>
                  <td>{l.reference_ms != null ? fmtLapTime(l.reference_ms) : "—"}</td>
                  <td>{fmtDeviation(l.deviation_ms)}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{l.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card card-pad">
        <div className="section-title">Summary</div>
        <div className="grid-2">
          <Stat label="Laps recorded" value={String(s.laps_recorded)} />
          <Stat
            label="Average deviation"
            value={s.comparable ? fmtDeviation(s.average_deviation_ms) : "No comparable laps"}
          />
          <Stat
            label="Largest deviation"
            value={s.largest_deviation_ms != null ? `${fmtDeviation(s.largest_deviation_ms)} (lap ${s.largest_deviation_lap})` : "—"}
          />
          <Stat
            label="Laps without a comparison"
            value={`${s.laps_without_comparison}${s.late_count > 0 ? ` · ${s.late_count} late` : ""}`}
          />
        </div>
      </div>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ padding: "6px 0" }}>
      <div className="muted" style={{ fontSize: 12 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function AssignPanel({ swim, timers, onChanged }: { swim: SwimDetail; timers: User[]; onChanged: () => void }) {
  const [timerId, setTimerId] = useState<number | "">("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const assign = async (e: FormEvent) => {
    e.preventDefault();
    if (timerId === "") return;
    setBusy(true);
    setErr(null);
    try {
      await api.assignTimer({ swim_id: swim.id, timer_id: Number(timerId) });
      setTimerId("");
      onChanged();
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Could not assign.");
    } finally {
      setBusy(false);
    }
  };

  const unassign = async () => {
    if (swim.assignment_id == null) return;
    setBusy(true);
    setErr(null);
    try {
      await api.unassign(swim.assignment_id);
      onChanged();
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Could not unassign.");
    } finally {
      setBusy(false);
    }
  };

  if (swim.status === SwimStatus.Closed) {
    return (
      <div className="card card-pad">
        <div className="section-title">Timer</div>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          {swim.assigned_timer_name ?? "—"} · assignments are locked on a closed swim.
        </p>
      </div>
    );
  }

  return (
    <div className="card card-pad">
      <div className="section-title">Timer</div>
      {swim.assigned_timer_id != null ? (
        <div className="row-between" style={{ marginBottom: 8 }}>
          <span>{swim.assigned_timer_name ?? `#${swim.assigned_timer_id}`}</span>
          <button className="btn btn-ghost btn-sm" onClick={unassign} disabled={busy}>Unassign</button>
        </div>
      ) : timers.length === 0 ? (
        <Notice kind="info">No timers enrolled yet. Add one from Accounts.</Notice>
      ) : (
        <form onSubmit={assign}>
          <div className="field">
            <label htmlFor="a-timer">Assign a timer</label>
            <select id="a-timer" value={timerId} onChange={(e) => setTimerId(e.target.value === "" ? "" : Number(e.target.value))}>
              <option value="">Select…</option>
              {timers.map((t) => (
                <option key={t.id} value={t.id}>{t.display_name}</option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn btn-primary btn-sm" disabled={busy || timerId === ""}>
            {busy ? <Spinner /> : "Assign timer"}
          </button>
        </form>
      )}
      {err && <div style={{ marginTop: 12 }}><Notice kind="error">{err}</Notice></div>}
    </div>
  );
}
