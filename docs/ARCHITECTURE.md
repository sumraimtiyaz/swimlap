# SwimLap — Architecture

> **⚠️ Partially superseded (2026-07-21).** This document describes the original
> reconstructed design (multi-lane *heats*, per-device NTP clock-offset
> reconciliation). The project was later **realigned to the recovered PRD**:
> single-swimmer *swims*, and a **server-authoritative clock** that stamps
> `server_ts` on arrival (buffered laps use `device_mono_ms` deltas) rather than
> the offset handshake below. The layering, DIP/ports-and-adapters structure, and
> the shared-contract story still hold; the domain model and clock sections do
> not. See each app's README for the current shape.

A single monorepo, three deployables, one shared contract.

```
swimlap/
├── backend/           FastAPI service (Python 3.12)
├── mobile/            Flutter timekeeper app
├── admin-dashboard/   React + TS coordinator console
├── shared/contracts/  contract.json — the single source of truth for the wire
├── docs/              this document + the reconstructed PRD
└── infra/             docker-compose, env samples
```

## 1. Why a monorepo

The backend and both clients change together whenever the wire changes. Keeping
them in one repo means a contract change and its three consumers land in one
reviewable commit, `shared/contracts/contract.json` has no cross-repo publishing
story to slow it down, and there is exactly one place to reason about the system.
Each app still builds and ships independently — the monorepo is about *coherence*,
not coupling.

## 2. Backend: clean/hexagonal layering

The dependency arrow points inward. Nothing in the centre knows about the web or
the database.

```
        HTTP (FastAPI routes, DTOs)
                  │ maps DomainError → HTTP, entity → DTO
                  ▼
            Services (use cases)
                  │ depend only on Protocols + domain
                  ▼
   Repository Protocols (Ports)      ◀── domain entities (pure dataclasses,
                  ▲                        state machine, timing math — zero deps)
        ┌─────────┴─────────┐
   In-memory adapter   SQLAlchemy adapter
   (tests + demo)      (production)
```

- **`domain/`** is pure Python: entities, the heat state machine, the clock-offset
  estimator, and lap validation. No FastAPI, no SQLAlchemy, no I/O. This is what
  makes the tricky parts unit-testable without a server or a database.
- **`services/`** hold the use cases and depend only on repository **Protocols**
  and the domain. They never learn whether persistence is Postgres or a dict —
  the **Dependency Inversion Principle** made concrete.
- **`repositories/`** provide two adapters behind the same Protocols. The
  **composition root** (`api/deps.py`) picks one based on `settings.persistence`
  (`memory` | `sqlalchemy`). This is the **Open/Closed seam**: a new backing store
  is a new adapter, not a change to services.
- **Interfaces are split by aggregate** (users, heats, timers, assignments, laps,
  clocks) — **Interface Segregation**: the lap service doesn't depend on user
  persistence.
- **`api/errors.py` is the only place business errors meet HTTP.** Services raise
  `DomainError(code)`; the handler maps codes to status and emits the uniform
  `{code, message, details}` envelope. A new error code is a one-line change.

The whole service layer is exercised in `tests/` against the in-memory adapter —
52 tests covering auth, the heat lifecycle, and (the crux) lap ingestion:
reconciliation, idempotent replay, scheduled-heat rejection, unassigned-timer
rejection, implausible-offset handling, buffered/late flagging, NaN persistence-
as-invalid, unordered batches, timer-completion closing the heat, and
inactivity auto-close.

## 3. The shared contract (DRY across three runtimes)

`shared/contracts/contract.json` is the single source of truth for wire-level
enums, error codes, and timing thresholds. All three runtimes derive their local
constants from it:

- **Backend** loads it at runtime (`domain/tuning.py`) and a test
  (`test_contract_sync`) asserts the Python enums still match the JSON.
- **Mobile** mirrors it in `core/contract.dart`.
- **Dashboard** mirrors it in `src/lib/contract.ts`.

The two client mirrors are **hand-kept today**. The intended end state is
**codegen**: a small build step reads `contract.json` and emits
`contract.dart` and `contract.ts`, so the mirrors can never drift and the JSON is
unambiguously the source. That step is deliberately deferred (it is tooling, not
product) but the file is already structured for it — flat enums, string error
codes, a `timing` tree of scalars. Until then, treat the JSON as authoritative
and update the mirrors alongside it; the backend's contract test is the tripwire.

## 4. Clock reconciliation (the defining decision)

**Problem.** Phones have skewed clocks and flaky signal, yet laps must land on one
timeline.

**Decision.** The *device* computes its own clock offset via an NTP-style
handshake against a stateless server echo endpoint, because the device is the
only party that holds all four handshake timestamps (t0 send, t1 server-recv,
t2 server-send, t3 recv). The estimator filters by minimum round-trip delay,
retains a bounded window of samples, and guards every value against
`NaN`/`Infinity`.

**But the server distrusts it.** On lap submission the device reports its offset;
the server validates the offset is finite and within a plausible bound, persists
it as a `DeviceClock` for audit, and uses the *trusted* offset to map each lap's
monotonic `device_mono_ms` to `server_ts_ms`. A lying or broken client can't
poison the timeline; at worst its laps are flagged invalid.

**Implemented once per runtime.** The identical algorithm lives in
`backend/app/domain/time_sync.py` and `mobile/lib/core/clock/time_sync_service.dart`,
derived from the same spec so both agree byte-for-byte on the math.

## 5. Offline-first capture

The mobile app treats the **local buffer as the capture source of truth** and the
server as eventually consistent. Every tap is persisted to `shared_preferences`
*before* upload; a `connectivity_plus` listener flushes batches on reconnect; the
server returns per-lap outcomes and acknowledged sequences are pruned.

This forces one non-obvious rule on the backend: **lap submission is accepted for
`live` *and* `closed` heats, rejected only for `scheduled`.** A lap captured while
a heat was live but synced seconds after it closed must not be lost. Each lap is
flagged `was_buffered` / `was_late` individually so the record stays honest. This
resolves a real tension in the source material (a "laps only while live" phrasing
coexisting with `was_buffered` / `was_late` fields).

Safe replay falls out of **idempotency on `(timer_id, seq)`** — enforced in the
service and backstopped by a DB unique constraint.

## 6. Live monitor: polling now, push later

The coordinator's live monitor **polls** `GET /admin/heats/{id}/laps` on a short
interval while a heat is live. Polling is the honest MVP: it is simple, stateless,
and correct. The seam is drawn so a later phase can swap the poll loop for
**Server-Sent Events or WebSocket** without the page changing shape — the monitor
hook (`useHeatMonitor`) is the only thing that would change, and the endpoint
already projects exactly the payload a push channel would send.

## 7. Persistence & migrations

The SQLAlchemy models (`models/`) use the 2.0 typed `Mapped` style and are
enum-as-string for forward compatibility. `create_all` is used for local/dev
bring-up; the intended production path is **Alembic** migrations (the models are
already the single schema definition, so wiring Alembic is mechanical). Postgres
is the target (`infra/docker-compose.yml`), with `psycopg` as the driver.

## 8. Decisions & assumptions (the log)

| # | Question in the source | Decision | Why |
|---|------------------------|----------|-----|
| 1 | Source PRD was garbled/reordered | Reconstruct from the technical fingerprint; flag everything as inferred | A buildable, reviewable system beats a refusal; honesty about provenance is preserved in `PRD_RECONSTRUCTED.md`. |
| 2 | `scheduled` / `live` / `active` all appeared | Collapse to `scheduled → live → closed` | `active` and `live` were synonyms for one state; three states cover the whole lifecycle without redundancy. |
| 3 | "Laps only while live" vs. `was_buffered`/`was_late` | Accept laps for `live` **and** `closed`; reject `scheduled`; flag each lap | Offline laps captured-while-live but synced-after-close must survive; flagging keeps the record truthful. |
| 4 | Who owns the clock offset? | Device computes; server validates + stores + applies | Only the device has all four handshake timestamps; the server must not trust an untrusted party. |
| 5 | What to do with implausible/NaN timing? | Persist the lap, mark `is_valid=false`, never drop | Audit integrity; scoring filters on validity. |
| 6 | Duplicate/retried laps | Idempotent on `(timer_id, seq)` | Makes offline buffer replay safe by construction. |
| 7 | How does a heat end? | `timer_completed` (all timers hit target) / `auto_inactivity` (~90s quiet) / `manual` | Covers the natural, the abandoned, and the deliberate endings the fragments implied. |
| 8 | Live updates | Poll now, SSE/WebSocket later | Simple and correct for the MVP; the seam is drawn for the upgrade. |
| 9 | Contract duplication across 3 apps | One JSON source; mirrors now, codegen later | DRY without prematurely building tooling; a test guards the backend mirror. |
| 10 | DI framework? | Manual composition root (backend) / service locator (mobile) | The systems are small enough that explicit wiring is clearer than a framework. |

## 9. Deferred to future phases

Scoring & results, real-time push, multi-meet/club tenancy, seeding/brackets,
spectator/read-only views, contract codegen, Alembic migration history, and
offline authentication. None require reworking the core: each is an additive
service, adapter, or route against the model already in place.
