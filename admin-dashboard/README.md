# SwimLap — Coordinator Console

React + TypeScript + Vite dashboard for **coordinators**. Timers use the Flutter
mobile app; this console is coordinator-only and refuses timer logins at the door.

## What it does

- **Sign in** as a coordinator (JWT stored in `localStorage`).
- **Accounts** — enrol a timer; the system generates the password and shows it
  **once** (it can never be retrieved again). Reset issues a new one; deactivate
  blocks login while keeping the account and its captures for past reports.
- **Setup** — add venues and swimmers, then schedule a **swim** (one swimmer, one
  lane, one timer). Assigning a timer to two overlapping swims is rejected.
- **Live view** — one row per live swim. **Connected** (presence) and **Laps**
  (capturing) are shown as separate signals, with a **stalled** warning when the
  lap count hasn't moved for longer than twice the typical lap time.
- **Report** — the per-lap table (Recorded / Cumulative / Reference / Deviation /
  Note) and the four summary numbers, computed on request and correct while the
  swim is still live. Every screen built on simulated data carries the
  **`SIMULATED DATA — NOT MEASURED TIMING`** banner (PRD §9).

## Run it

Requires Node 18+.

```bash
cd admin-dashboard
npm install
# point at your backend (defaults to http://localhost:8000):
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.local
npm run dev          # http://localhost:5173
```

Type-check / production build:

```bash
npm run build        # tsc -b && vite build
```

> The backend seeds a coordinator on first start (`coordinator` / `swimlap-admin`
> by default — see `backend/.env.example`). Sign in with those, then enrol timers
> from **Accounts**.

## Layout

```
src/
├── lib/
│   ├── contract.ts     # hand-kept mirror of shared/contracts/contract.json
│   └── format.ts       # lap-time / deviation formatting (never renders NaN)
├── api/
│   ├── types.ts        # wire types mirroring backend pydantic schemas
│   └── client.ts       # fetch wrapper: bearer auth + {code,message} envelope
├── hooks/
│   ├── useAuth.tsx     # session context; token persistence; role guard
│   └── useSwims.ts     # swim list + live-view poll + report poll
├── components/ui.tsx   # header, swim badge, spinner, notices (shared, stateless)
├── pages/
│   ├── LoginPage.tsx
│   ├── DashboardPage.tsx    # live view + swim list + setup rail
│   ├── SwimDetailPage.tsx   # assign, live status, report + banner, close
│   └── AccountsPage.tsx     # create (one-time password), reset, deactivate
├── App.tsx             # auth-gated routes
├── main.tsx            # providers + entry
└── index.css           # design tokens + component styles
```

## Boundaries (SOLID/DRY)

- **`client.ts` is the only module that touches `fetch`.** Hooks and pages deal
  in domain types; the HTTP envelope and bearer token live in one place.
- **`contract.ts` mirrors the shared contract** so enum spellings and error codes
  match the backend and mobile app.
- **The token source is injected** into the client (`configureAuth`) rather than
  read from storage inside it, so persistence is swappable without touching the
  transport layer.
