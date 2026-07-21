# SwimLap — Reconstructed Product Requirements

> **⚠️ SUPERSEDED (2026-07-21).** The original, readable PRD was later recovered.
> The project has been **realigned to that PRD**: a single **swimmer**'s practice
> **swim** (one swimmer, one lane, one **timer**), a simulated **reference** per
> lap, and a deviation **report** — not the multi-lane swim-meet model this
> document inferred. The server now stamps `server_ts` on arrival (buffered laps
> use `device_mono_ms` deltas) instead of the NTP clock-offset scheme described in
> §4 below. This file is kept only as a record of the original reconstruction; the
> authoritative spec is the delivered `swimlap_full_text` PRD. Sections below no
> longer match the code (entities: `venues`/`swimmers`/`swims`/`reference_laps`;
> endpoints under `/swims`, `/users`, `/venues`, `/swimmers`).

> **Read this first.** The source file provided (`swimlap_reordered.pdf`) did not
> arrive as readable requirements prose. Its text reached the build as
> **scrambled, reordered word fragments** (the filename itself says
> `_reordered`), and the original PDF was not recoverable from disk. The literal
> requirements could not be read back verbatim.
>
> Rather than refuse, this document reconstructs a **coherent, buildable spec**
> by treating the fragments as a *technical fingerprint* — the recurring nouns,
> endpoint shapes, field names, and state words that survived the scramble. The
> result below is an **inference**, not a transcription. Every section should be
> confirmed against the intended requirements; anywhere the reconstruction had to
> make a call, it is flagged in `ARCHITECTURE.md` under "Decisions & assumptions".

## 1. Product in one line

A **swim-meet lap-timing platform**: timekeepers stationed at lanes tap to record
laps on a phone; a coordinator schedules heats, assigns timekeepers, runs the
heat, and watches laps arrive live — with the whole system disciplined around
*accurate time* despite unreliable pool-deck connectivity.

## 2. Actors

| Actor | Surface | Does |
|-------|---------|------|
| **Coordinator** | Web console | Enrolls timekeepers, schedules heats, assigns lanes, starts/closes heats, monitors laps, runs the simulator. |
| **Timekeeper** | Mobile app | Signs in, sees assigned heats, taps to record laps for their lane (offline-capable). |

Authentication is email + password via `POST /auth/login`, returning a bearer
token. Roles gate every route.

## 3. Core domain

### Heats
A heat has a name, a scheduled start, a lane count, and a target lap count. Its
lifecycle is a three-state machine:

```
scheduled ──start──▶ live ──close──▶ closed
```

*(Source fragments showed both "active" and "live"; these were collapsed to a
single `live` state — see the decision log.)*

A heat closes three ways, recorded as `closure_method`:
- `timer_completed` — every assigned timer reached the target lap count,
- `auto_inactivity` — no laps arrived for the inactivity window (~90s), auto-closed,
- `manual` — the coordinator closed it.

### Timers
Creating a heat materialises one **timer per lane**. A timer has a lane number,
an optional assigned timekeeper, a state (`pending → running → completed`), and a
lap count. A timer completes when it reaches the heat's target laps.

### Laps
The heart of the system. Each lap carries:
- `seq` — per-timer sequence number (idempotency key with `timer_id`),
- `device_mono_ms` — a **monotonic** device timestamp (not wall clock),
- `server_ts_ms` — the reconciled server-time estimate,
- `is_valid` — whether timing values were finite/plausible,
- `was_late` — arrived after a grace threshold,
- `was_buffered` — captured offline and synced later,
- `source` — `manual` (a real tap) or `simulated` (demo/QA).

**Invalid laps are flagged, never dropped** — the audit trail keeps everything;
scoring filters on `is_valid`.

## 4. The hard problem: distributed clock reconciliation

Phones on a pool deck have skewed clocks and flaky signal. The system must place
laps on a common timeline anyway.

- The device runs an **NTP-style handshake** against a stateless server echo
  endpoint and computes its own clock **offset** (round-trip / delay filtered),
  because the device is the only party holding all four handshake timestamps.
- The server **does not trust** the reported offset blindly: it validates the
  offset is finite and within a plausible bound, stores it for audit, and uses it
  to map each lap's `device_mono_ms` to `server_ts_ms`.
- All timing values are guarded against `NaN`/`Infinity` at every boundary.

The offset algorithm is implemented **once per runtime** (Python service + Dart
client) from the same specification, so both agree.

## 5. Offline capture

Timekeepers must be able to record laps with no connectivity:
- Every tap is written to a **durable local buffer before upload**.
- Batches sync when connectivity returns; the server reconciles and returns
  per-lap outcomes; acknowledged sequences are pruned.
- Because laps are idempotent on `(timer_id, seq)`, replaying a stale buffer is
  safe.

This is why the lap-submission rule accepts laps for a heat that is `live` **or**
`closed` (rejecting only `scheduled`): a lap captured while the heat was live but
synced moments after it closed must not be lost. See the decision log — this
resolves a genuine tension in the source fragments (`laps only while live`
vs. the existence of `was_buffered` / `was_late`).

## 6. API surface (as built)

```
POST /auth/login                      → { token, user }

# timekeeper
GET  /my-heats                        → heats the caller is assigned to
POST /heats/{id}/laps                 → submit a batch; returns per-lap outcomes
POST /clock/echo                      → stateless time handshake

# coordinator (all under /admin, role-gated)
POST /admin/users                     → enroll a user
GET  /admin/users?role=timekeeper     → list users (populates the lane picker)
GET  /admin/heats                     → list heats
POST /admin/heats                     → schedule a heat (materialises lane timers)
GET  /admin/heats/{id}                → heat detail + timers
POST /admin/heats/{id}/assignments    → assign a timekeeper to a lane
POST /admin/heats/{id}/start          → scheduled → live
POST /admin/heats/{id}/close          → live → closed (manual)
GET  /admin/heats/{id}/laps           → live-monitor feed (polled)
POST /admin/heats/{id}/simulate       → drive simulated laps across lanes
```

Errors use a uniform `{ code, message, details }` envelope.

## 7. Explicitly out of scope for the MVP

Scoring/results/rankings, real-time push (SSE/WebSocket) for the monitor,
multi-meet/club tenancy, heat brackets/seeding, spectator views, push
notifications, and offline auth. Each is a clean extension of the current model —
see `ARCHITECTURE.md`.
