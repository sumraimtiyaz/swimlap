"""Reference lap service.

Thin wrapper over the pure generator (``domain/reference``) + persistence. A
reference is created for lap *n* when lap *n* arrives (called from the lap ingest
path), never batched at the end — the report must work while a swim runs. Every
row carries ``source = 'simulated'``. Idempotent: re-arrival of the same lap does
not regenerate its reference.
"""
from __future__ import annotations

import random

from app.domain.entities import ReferenceLap
from app.domain.reference import generate_reference
from app.domain.tuning import ReferenceTuning
from app.repositories.interfaces import ReferenceLapRepository


class ReferenceService:
    def __init__(self, references: ReferenceLapRepository, tuning: ReferenceTuning, rng: random.Random | None = None):
        self._refs = references
        self._tuning = tuning
        self._rng = rng or random.Random()

    def ensure_for_lap(self, swim_id: int, lap_no: int) -> ReferenceLap:
        existing = self._refs.get(swim_id, lap_no)
        if existing is not None:
            return existing
        elapsed_ms, is_valid = generate_reference(self._tuning, self._rng)
        return self._refs.upsert(ReferenceLap(
            id=0, swim_id=swim_id, lap_no=lap_no, elapsed_ms=elapsed_ms,
            is_valid=is_valid, source="simulated",
        ))
