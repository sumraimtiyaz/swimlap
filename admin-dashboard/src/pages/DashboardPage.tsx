/**
 * Coordinator home: the live view up top (one row per live swim, presence vs.
 * capturing shown separately, with a stalled warning), the full swim list, and
 * the setup rail (schedule a swim, add venues/swimmers).
 */
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { useLiveSwims, useSwims } from "../hooks/useSwims";
import { AppHeader, Empty, Notice, Spinner, SwimBadge } from "../components/ui";
import { fmtLapTime, fmtClockTime } from "../lib/format";
import type { Swim, Swimmer, Venue } from "../api/types";

export function DashboardPage() {
  const { swims, loading, error, reload } = useSwims();
  const [venues, setVenues] = useState<Venue[]>([]);
  const [swimmers, setSwimmers] = useState<Swimmer[]>([]);

  const loadSetup = useCallback(async () => {
    try {
      const [v, s] = await Promise.all([api.listVenues(), api.listSwimmers()]);
      setVenues(v);
      setSwimmers(s);
    } catch {
      /* surfaced by individual forms */
    }
  }, []);

  useEffect(() => {
    void loadSetup();
  }, [loadSetup]);

  return (
    <>
      <AppHeader />
      <main className="page">
        <div className="page-head">
          <div>
            <div className="eyebrow">Meet control</div>
            <h1>Swims</h1>
          </div>
        </div>

        <LiveNow />

        <div className="grid-2">
          <section className="stack">
            {loading && (
              <div className="card card-pad row-gap">
                <Spinner /> <span className="muted">Loading swims…</span>
              </div>
            )}
            {error && <Notice kind="error">{error}</Notice>}
            {!loading && !error && swims.length === 0 && (
              <div className="card">
                <Empty>No swims yet. Schedule one from the panel on the right.</Empty>
              </div>
            )}
            {swims.map((swim) => (
              <SwimCard key={swim.id} swim={swim} />
            ))}
          </section>

          <aside className="stack">
            <ScheduleSwimPanel venues={venues} swimmers={swimmers} onCreated={reload} />
            <AddVenuePanel onCreated={loadSetup} />
            <AddSwimmerPanel onCreated={loadSetup} />
          </aside>
        </div>
      </main>
    </>
  );
}

function LiveNow() {
  const { rows, error } = useLiveSwims();
  if (error) return null;
  if (rows.length === 0) return null;
  return (
    <div className="card card-pad" style={{ marginBottom: 20 }}>
      <div className="section-title">Live now</div>
      <div style={{ overflowX: "auto" }}>
        <table className="log">
          <thead>
            <tr>
              <th>Swimmer</th>
              <th>Lane</th>
              <th>Timer</th>
              <th>Connected</th>
              <th>Laps</th>
              <th>Last lap</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.swim_id}>
                <td>
                  <Link to={`/swims/${r.swim_id}`}>{r.swimmer_name}</Link>
                </td>
                <td>{r.lane_no}</td>
                <td>{r.timer_name ?? "—"}</td>
                <td>
                  <span className={r.connected ? "flag flag-ok" : "flag flag-late"}>
                    {r.connected ? "Yes" : "No"}
                  </span>
                </td>
                <td>{r.lap_count}</td>
                <td>{fmtLapTime(r.last_lap_ms)}</td>
                <td>
                  {r.stalled ? (
                    <span className="flag flag-invalid">⚠ stalled</span>
                  ) : (
                    <span className="muted">running</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SwimCard({ swim }: { swim: Swim }) {
  const target = swim.lap_target != null ? ` · target ${swim.lap_target}` : "";
  return (
    <Link to={`/swims/${swim.id}`} className="heat-row">
      <div className="heat-row-main">
        <div className="heat-row-name">{swim.swimmer_name}</div>
        <div className="heat-row-meta mono">
          {swim.venue_name} · Lane {swim.lane_no} · {fmtClockTime(swim.scheduled_start)}{target}
        </div>
      </div>
      <SwimBadge state={swim.status} />
    </Link>
  );
}

// --- setup panels ----------------------------------------------------------
function ScheduleSwimPanel({
  venues,
  swimmers,
  onCreated,
}: {
  venues: Venue[];
  swimmers: Swimmer[];
  onCreated: () => void;
}) {
  const [venueId, setVenueId] = useState<number | "">("");
  const [swimmerId, setSwimmerId] = useState<number | "">("");
  const [lane, setLane] = useState(1);
  const [start, setStart] = useState(defaultStartLocal);
  const [target, setTarget] = useState<number | "">(20);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const venue = venues.find((v) => v.id === venueId);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (venueId === "" || swimmerId === "") return;
    setBusy(true);
    setErr(null);
    setOk(null);
    try {
      const swim = await api.createSwim({
        venue_id: Number(venueId),
        swimmer_id: Number(swimmerId),
        lane_no: lane,
        scheduled_start: new Date(start).toISOString(),
        lap_target: target === "" ? null : Number(target),
      });
      setOk(`Scheduled ${swim.swimmer_name} in lane ${swim.lane_no}.`);
      onCreated();
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Could not schedule swim.");
    } finally {
      setBusy(false);
    }
  };

  const disabled = venues.length === 0 || swimmers.length === 0;

  return (
    <div className="card card-pad">
      <div className="section-title">Schedule a swim</div>
      {disabled && <Notice kind="info">Add a venue and a swimmer first.</Notice>}
      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="s-venue">Venue</label>
          <select id="s-venue" value={venueId} onChange={(e) => setVenueId(e.target.value === "" ? "" : Number(e.target.value))}>
            <option value="">Select…</option>
            {venues.map((v) => (
              <option key={v.id} value={v.id}>{v.name} ({v.lane_count} lanes)</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="s-swimmer">Swimmer</label>
          <select id="s-swimmer" value={swimmerId} onChange={(e) => setSwimmerId(e.target.value === "" ? "" : Number(e.target.value))}>
            <option value="">Select…</option>
            {swimmers.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
        <div className="field-row">
          <div className="field">
            <label htmlFor="s-lane">Lane</label>
            <input id="s-lane" type="number" min={1} max={venue?.lane_count ?? 64} value={lane}
              onChange={(e) => setLane(Number(e.target.value))} />
          </div>
          <div className="field">
            <label htmlFor="s-target">Lap target</label>
            <input id="s-target" type="number" min={1} max={500} value={target}
              onChange={(e) => setTarget(e.target.value === "" ? "" : Number(e.target.value))} />
          </div>
        </div>
        <div className="field">
          <label htmlFor="s-start">Scheduled start</label>
          <input id="s-start" type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
        </div>

        {err && <div style={{ marginBottom: 12 }}><Notice kind="error">{err}</Notice></div>}
        {ok && <div style={{ marginBottom: 12 }}><Notice kind="info">{ok}</Notice></div>}

        <button type="submit" className="btn btn-primary" disabled={busy || disabled || venueId === "" || swimmerId === ""}>
          {busy ? <Spinner /> : "Schedule swim"}
        </button>
      </form>
    </div>
  );
}

function AddVenuePanel({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [lanes, setLanes] = useState(8);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.createVenue({ name: name.trim(), lane_count: lanes });
      setName("");
      onCreated();
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Could not add venue.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card card-pad">
      <div className="section-title">Add a venue</div>
      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="v-name">Name</label>
          <input id="v-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Aqua Center" />
        </div>
        <div className="field">
          <label htmlFor="v-lanes">Lane count</label>
          <input id="v-lanes" type="number" min={1} max={64} value={lanes} onChange={(e) => setLanes(Number(e.target.value))} />
        </div>
        {err && <div style={{ marginBottom: 12 }}><Notice kind="error">{err}</Notice></div>}
        <button type="submit" className="btn btn-ghost btn-sm" disabled={busy || name.trim().length === 0}>
          {busy ? <Spinner /> : "Add venue"}
        </button>
      </form>
    </div>
  );
}

function AddSwimmerPanel({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.createSwimmer({ name: name.trim() });
      setName("");
      onCreated();
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Could not add swimmer.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card card-pad">
      <div className="section-title">Add a swimmer</div>
      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="sw-name">Name</label>
          <input id="sw-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Alex Rivera" />
        </div>
        {err && <div style={{ marginBottom: 12 }}><Notice kind="error">{err}</Notice></div>}
        <button type="submit" className="btn btn-ghost btn-sm" disabled={busy || name.trim().length === 0}>
          {busy ? <Spinner /> : "Add swimmer"}
        </button>
      </form>
    </div>
  );
}

function defaultStartLocal(): string {
  const d = new Date(Date.now() + 10 * 60_000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
