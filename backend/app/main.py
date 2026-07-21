"""SwimLap API application factory.

Wires routers, error handling, CORS, startup seeding, and a background inactivity
monitor. Persistence is chosen by config; in ``memory`` mode a single shared repo
bundle lives on ``app.state`` so data survives across requests within the process.
"""
from __future__ import annotations

import asyncio
import contextlib
import importlib
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import Repositories, build_repositories, build_services
from app.api.errors import register_error_handlers
from app.api.routes import auth, coordinator, timer
from app.core.config import get_settings
from app.core.security import BcryptPasswordHasher
from app.domain.entities import User
from app.domain.enums import SwimStatus, UserRole

logger = logging.getLogger("swimlap")


def _seed_coordinator(repos: Repositories) -> None:
    settings = get_settings()
    if not settings.seed_coordinator_password:
        return
    username = settings.seed_coordinator_username.strip().lower()
    if repos.users.get_by_username(username) is not None:
        return
    repos.users.add(User(
        id=0, username=username, display_name="Coordinator", role=UserRole.COORDINATOR,
        hashed_password=BcryptPasswordHasher().hash(settings.seed_coordinator_password),
        is_active=True,
    ))
    logger.info("Seeded coordinator account %s", username)


def _build_memory_repos() -> Repositories:
    return build_repositories(None, get_settings())


async def _inactivity_monitor(app: FastAPI) -> None:
    """Periodically auto-close live swims that have gone quiet.

    Kept intentionally simple (poll loop). Each tick builds a fresh service graph
    so it uses whichever persistence is configured. Failures are logged, never
    fatal.
    """
    settings = get_settings()
    while True:
        await asyncio.sleep(15)
        try:
            if settings.persistence == "memory":
                repos = app.state.memory_repos
                services = build_services(repos, settings)
                for swim in repos.swims.list_by_status(SwimStatus.LIVE):
                    services.swims.auto_close_if_inactive(swim.id)
            else:
                from app.db.session import SessionLocal
                with SessionLocal() as session:
                    repos = build_repositories(session, settings)
                    services = build_services(repos, settings)
                    for swim in repos.swims.list_by_status(SwimStatus.LIVE):
                        services.swims.auto_close_if_inactive(swim.id)
                    session.commit()
        except Exception:  # pragma: no cover - defensive background loop
            logger.exception("inactivity monitor tick failed")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="SwimLap API", version="2.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    for module in (auth, coordinator, timer):
        app.include_router(module.router)

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        return {"status": "ok", "persistence": settings.persistence}

    @app.on_event("startup")
    async def _startup() -> None:
        if settings.persistence == "memory":
            app.state.memory_repos = _build_memory_repos()
            _seed_coordinator(app.state.memory_repos)
        else:
            from app.db.session import Base, SessionLocal, engine
            importlib.import_module("app.models")   # noqa: F401  (registers tables on the metadata)
            Base.metadata.create_all(bind=engine)
            with SessionLocal() as session:
                repos = build_repositories(session, settings)
                _seed_coordinator(repos)
                session.commit()

        app.state.monitor_task = asyncio.create_task(_inactivity_monitor(app))

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        task = getattr(app.state, "monitor_task", None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    return app


app = create_app()
