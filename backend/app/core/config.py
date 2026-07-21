"""Runtime configuration.

Twelve-factor: everything that varies between environments comes from env vars
(or a local ``.env``). ``PERSISTENCE`` chooses the repository adapter at boot —
the one place the DIP wiring is selected — so tests/demos can run fully in memory
while production uses Postgres, with no code change anywhere else.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SWIMLAP_", env_file=".env", extra="ignore")

    environment: Literal["dev", "test", "prod"] = "dev"
    persistence: Literal["memory", "sqlalchemy"] = "sqlalchemy"

    database_url: str = "postgresql+psycopg://swimlap:swimlap@localhost:5432/swimlap"

    jwt_secret: str = Field(default="change-me-in-prod", min_length=8)
    jwt_algorithm: str = "HS256"
    # 24h covers a practice day (PRD §4). Mirrors contract auth.tokenTtlHours.
    jwt_ttl_minutes: int = 24 * 60

    cors_allow_origins: list[str] = ["http://localhost:5173"]

    # Seed a first coordinator on empty databases so the system is usable
    # immediately. Disable in prod by leaving the password blank.
    seed_coordinator_username: str = "coordinator"
    seed_coordinator_password: str = "swimlap-admin"


@lru_cache
def get_settings() -> Settings:
    return Settings()
