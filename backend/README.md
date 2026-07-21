# SwimLap Backend

FastAPI service with a **framework-agnostic domain core**. The interesting logic
(swim state machine, lap validation, the simulated reference generator, and the
deviation report) lives in `app/domain/` and depends on nothing but the standard
library, so it is unit-tested without a database or web server.

## Layout

```
app/
  domain/        # pure business logic + entities (no FastAPI/SQLAlchemy) — tested directly
                 #   state_machine, validation, reference, report, numeric guards
  repositories/  # interfaces (Ports) + memory & sqlalchemy adapters (DIP)
  services/      # orchestration; depends only on Ports + domain
  models/        # SQLAlchemy tables: users, venues, swimmers, swims, assignments,
                 #   laps, reference_laps
  schemas/       # pydantic request/response DTOs
  api/           # FastAPI routes, DI composition root, error mapping
  core/          # config, security (bcrypt/JWT, password generator), system clock
```

## Two rules that govern timing (PRD §2)

- **The server clock is the only clock that counts.** `server_ts` is stamped the
  instant a capture arrives (before validation) and is the basis for live lap
  times (`lap_n = server_ts_n − server_ts_(n-1)`).
- **Buffered laps are the exception.** A whole offline queue arrives in one
  instant, so a lap flagged `was_buffered` is timed from the `device_mono_ms`
  delta instead. All timestamps are stored in UTC.

## Run it

### Option A — zero-dependency demo (in-memory, no Postgres)
```bash
pip install -e .
SWIMLAP_PERSISTENCE=memory uvicorn app.main:app --reload
# open http://localhost:8000/docs  — sign in as coordinator / swimlap-admin
```

### Option B — with Postgres
```bash
cp .env.example .env         # then edit
pip install -e .
uvicorn app.main:app --reload
```

Or from the repo root: `cd infra && docker compose up` (Postgres + this API).

## Tests
```bash
python -m unittest discover -s tests -t .    # 46 tests, no extra deps required
```

> Note: this environment's `fastapi`/`starlette` pairing is missing `httpx`, so
> `TestClient`/`pytest` need `pip install httpx` and a matching `starlette` to
> run. The stdlib `unittest` suite covers the domain + services with no such
> dependency; the HTTP layer is verified by running uvicorn directly.

## The API in one glance

Auth (public):
- `POST /auth/login` → `{ token, user }`

Coordinator:
- `POST /users`, `POST /users/{id}/reset-password`, `PATCH /users/{id}/deactivate`, `GET /users`
- `POST /venues`, `GET /venues`, `POST /swimmers`, `GET /swimmers`
- `POST /swims`, `GET /swims`, `GET /swims/{id}`
- `POST /assignments`, `DELETE /assignments/{id}`
- `POST /swims/{id}/close`, `GET /swims/live`, `GET /swims/{id}/report`
- `POST /swims/{id}/simulate` (demo — inject taps that drive the real ingest path)

Timer:
- `GET /my-swims` (scheduled/live only — a closed swim is never returned)
- `GET /swims/{id}/state` (resume), `POST /swims/{id}/laps` (idempotent batch)
- `POST /swims/{id}/complete`, `POST /swims/{id}/liveness`

Every endpoint except `/auth/login` requires a token; each checks, in order,
valid token (401) → correct role (403) → record ownership (403).

## Note on migrations

For the MVP, tables are created via `Base.metadata.create_all` at startup. The
realignment is a breaking schema change, so an existing database must be recreated
(or migrated with Alembic — the models are structured for it).
