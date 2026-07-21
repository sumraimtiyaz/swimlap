/** Shared display formatting for times and deviations. */

/** A lap/elapsed time in ms → "42.13s" or "1:02.13". */
export function fmtLapTime(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return "—";
  const total = Math.round(ms);
  const m = Math.floor(total / 60000);
  const s = (total % 60000) / 1000;
  return m > 0 ? `${m}:${s.toFixed(2).padStart(5, "0")}s` : `${s.toFixed(2)}s`;
}

/** A signed deviation in ms → "+0.30s" / "−0.12s". Never renders NaN. */
export function fmtDeviation(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return "—";
  const s = ms / 1000;
  const sign = s > 0 ? "+" : s < 0 ? "−" : "±";
  return `${sign}${Math.abs(s).toFixed(2)}s`;
}

/** ISO timestamp → local short date/time. */
export function fmtClockTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
