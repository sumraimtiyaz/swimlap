/**
 * Data-loading hooks for swims.
 *
 * These wrap the API client with the React glue every screen needs — loading
 * flags, error capture, abort on unmount, and (for the live view + report) a
 * polling loop. Pages stay declarative; the fetch/poll mechanics live here.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError } from "../api/client";
import type { LiveRow, Report, Swim } from "../api/types";

interface SwimsState {
  swims: Swim[];
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useSwims(): SwimsState {
  const [swims, setSwims] = useState<Swim[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    api
      .listSwims(controller.signal)
      .then((data) => {
        setSwims(sortSwims(data));
        setError(null);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        setError(err instanceof ApiError ? err.message : "Could not load swims.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [nonce]);

  return { swims, loading, error, reload };
}

/** Live first, then scheduled by start time, then closed last. */
function sortSwims(swims: Swim[]): Swim[] {
  const rank: Record<string, number> = { live: 0, scheduled: 1, closed: 2 };
  return [...swims].sort((a, b) => {
    const byState = (rank[a.status] ?? 9) - (rank[b.status] ?? 9);
    if (byState !== 0) return byState;
    return a.scheduled_start.localeCompare(b.scheduled_start);
  });
}

/** Polls `GET /swims/live` — presence + capturing for every live swim (§8.3). */
export function useLiveSwims(intervalMs = 3000): { rows: LiveRow[]; error: string | null } {
  const [rows, setRows] = useState<LiveRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      const controller = new AbortController();
      try {
        const data = await api.liveSwims(controller.signal);
        if (!cancelled) {
          setRows(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Live feed unavailable.");
      } finally {
        if (!cancelled) timer = setTimeout(tick, intervalMs);
      }
    };
    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [intervalMs]);

  return { rows, error };
}

/** Polls the report while a swim is live; one-shot when closed. */
export function useSwimReport(
  swimId: number,
  active: boolean,
  intervalMs = 2500,
): { report: Report | null; error: string | null; initialLoading: boolean } {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const seen = useRef(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      const controller = new AbortController();
      try {
        const data = await api.getReport(swimId, controller.signal);
        if (cancelled) return;
        setReport(data);
        setError(null);
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Report unavailable.");
      } finally {
        if (!cancelled) {
          seen.current = true;
          setInitialLoading(false);
          if (active) timer = setTimeout(tick, intervalMs);
        }
      }
    };
    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [swimId, active, intervalMs]);

  return { report, error, initialLoading };
}
