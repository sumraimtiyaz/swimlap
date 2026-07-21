# SwimLap

A practice **lap-timing platform**. A **timer** stands at a lane and watches one
swimmer; each time the swimmer completes a lap the timer taps, confirms, and the
server records the exact time and compares it against a simulated **reference**.
The difference is the **deviation**. A **coordinator** enrols timers, schedules
swims, watches them live, and reads the deviation report (web console). The whole
system is disciplined around *accurate time* despite unreliable pool-deck
connectivity.

> **Provenance note.** The original PRD first arrived scrambled and the project
> was built to a reconstructed, multi-lane *swim-meet* inference. The real PRD was
> later recovered and the codebase has been **realigned** to it: one swimmer, one
> lane, one timer per **swim**; a simulated reference per lap; a deviation report.
> `docs/PRD_RECONSTRUCTED.md` is retained only as a record and is marked
> superseded.

## Monorepo layout

```
swimlap/
├── backend/           FastAPI service (Python 3.12) — the source of truth for behavior
├── mobile/            Flutter timer app (offline-first tap-to-record)
├── admin-dashboard/   React + TS coordinator console (accounts, setup, live view, report)
├── shared/contracts/  contract.json — single source of truth for the wire
├── docs/              architecture / decision log (+ superseded reconstruction)
└── infra/             docker-compose (Postgres + API), env samples
```

Each app has its own README with setup details. Start with the backend.

## Quick start (backend, zero external services)

The backend runs in-memory by default — no database needed to try it.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
SWIMLAP_PERSISTENCE=memory uvicorn app.main:app --reload   # http://localhost:8000  (docs at /docs)
```

A coordinator is seeded on first start (`coordinator` / `swimlap-admin` by
default — override via `SWIMLAP_SEED_COORDINATOR_USERNAME` / `..._PASSWORD`).

Run the test suite (pure-stdlib, no pytest required):

```bash
cd backend
python -m unittest discover -s tests -t .      # 46 tests
```

Then bring up the clients:

- **Coordinator console** — `cd admin-dashboard && npm install && npm run dev`
  (see `admin-dashboard/README.md`).
- **Timer app** — `cd mobile && flutter create . && flutter pub get && flutter run`
  (see `mobile/README.md`).

## Full stack with Postgres

```bash
cd infra
cp .env.example .env
docker compose up --build      # Postgres + API on :8000  (SWIMLAP_PERSISTENCE=sqlalchemy)
```

## What's inside (highlights)

- **Clean/hexagonal backend** — a pure domain core (`app/domain/`), repository
  Protocols, and two interchangeable persistence adapters selected at the
  composition root. The interesting logic (swim state machine, lap validation,
  the deviation **report engine**, the simulated **reference** generator) is
  framework-free and unit-tested without a database.
- **The server clock is the only clock that counts** — `server_ts` is stamped on
  arrival; live lap times are `server_ts` deltas, and buffered (offline) laps are
  timed from `device_mono_ms` deltas so a whole queue uploaded at once still
  computes correct lap times.
- **Offline-first capture** — every confirmed tap is durably buffered before
  upload; laps sync on reconnect; idempotent on `(timer_id, swim_id, seq)` so
  replay is safe; bad laps are flagged, never dropped.
- **Accounts are issued, never self-created** — the system generates a one-time
  password; reset/deactivate revoke every live token immediately.
- **One shared contract** — enums, error codes, and thresholds live in
  `shared/contracts/contract.json`; all three apps derive from it (DRY).

## Status

- **Backend** — complete and verified: 46 unit tests + a 38-check end-to-end HTTP
  run of the full flow (login → setup → capture → report → complete → revocation).
- **Dashboard** — complete and verified: type-checks, production-builds, and the
  live UI was driven end-to-end against the backend (live view, report + banner,
  one-time-password account creation).
- **Mobile** — complete Dart source with a `flutter test` unit suite for the
  capture/confirmation logic; run `flutter create .` + `flutter pub get` to
  generate platform folders and build on a device (no Flutter SDK was available
  in the build environment, so the app itself was not compiled here).
