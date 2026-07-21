"""In-memory repository adapters.

Back the service tests and an optional ``PERSISTENCE=memory`` demo mode (so the
API can be exercised end-to-end without Postgres). They store domain entities
directly. Not for production — no durability — but they satisfy the exact same
Protocols as the SQLAlchemy adapters, which is the point.
"""
from __future__ import annotations

import itertools
from dataclasses import replace

from app.domain.entities import Assignment, Lap, ReferenceLap, Swim, Swimmer, User, Venue
from app.domain.enums import SwimStatus


class _Sequence:
    def __init__(self) -> None:
        self._counter = itertools.count(1)

    def next(self) -> int:
        return next(self._counter)


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._by_id: dict[int, User] = {}
        self._seq = _Sequence()

    def get_by_username(self, username: str) -> User | None:
        return next((u for u in self._by_id.values() if u.username == username), None)

    def get_by_id(self, user_id: int) -> User | None:
        return self._by_id.get(user_id)

    def add(self, user: User) -> User:
        stored = replace(user, id=user.id or self._seq.next())
        self._by_id[stored.id] = stored
        return stored

    def update(self, user: User) -> User:
        self._by_id[user.id] = user
        return user

    def list_all(self) -> list[User]:
        return sorted(self._by_id.values(), key=lambda u: u.id)


class InMemoryVenueRepository:
    def __init__(self) -> None:
        self._by_id: dict[int, Venue] = {}
        self._seq = _Sequence()

    def get(self, venue_id: int) -> Venue | None:
        return self._by_id.get(venue_id)

    def add(self, venue: Venue) -> Venue:
        stored = replace(venue, id=venue.id or self._seq.next())
        self._by_id[stored.id] = stored
        return stored

    def list_all(self) -> list[Venue]:
        return sorted(self._by_id.values(), key=lambda v: v.id)


class InMemorySwimmerRepository:
    def __init__(self) -> None:
        self._by_id: dict[int, Swimmer] = {}
        self._seq = _Sequence()

    def get(self, swimmer_id: int) -> Swimmer | None:
        return self._by_id.get(swimmer_id)

    def add(self, swimmer: Swimmer) -> Swimmer:
        stored = replace(swimmer, id=swimmer.id or self._seq.next())
        self._by_id[stored.id] = stored
        return stored

    def list_all(self) -> list[Swimmer]:
        return sorted(self._by_id.values(), key=lambda s: s.id)


class InMemorySwimRepository:
    def __init__(self) -> None:
        self._by_id: dict[int, Swim] = {}
        self._seq = _Sequence()

    def get(self, swim_id: int) -> Swim | None:
        return self._by_id.get(swim_id)

    def add(self, swim: Swim) -> Swim:
        stored = replace(swim, id=swim.id or self._seq.next())
        self._by_id[stored.id] = stored
        return stored

    def update(self, swim: Swim) -> Swim:
        self._by_id[swim.id] = swim
        return swim

    def list_all(self) -> list[Swim]:
        return sorted(self._by_id.values(), key=lambda s: s.scheduled_start)

    def list_by_status(self, status: SwimStatus) -> list[Swim]:
        return [s for s in self._by_id.values() if s.status is status]


class InMemoryAssignmentRepository:
    def __init__(self) -> None:
        self._by_id: dict[int, Assignment] = {}
        self._seq = _Sequence()

    def add(self, assignment: Assignment) -> Assignment:
        stored = replace(assignment, id=assignment.id or self._seq.next())
        self._by_id[stored.id] = stored
        return stored

    def delete(self, assignment_id: int) -> None:
        self._by_id.pop(assignment_id, None)

    def get(self, assignment_id: int) -> Assignment | None:
        return self._by_id.get(assignment_id)

    def get_for_swim(self, swim_id: int) -> Assignment | None:
        return next((a for a in self._by_id.values() if a.swim_id == swim_id), None)

    def list_for_timer(self, timer_id: int) -> list[Assignment]:
        return [a for a in self._by_id.values() if a.timer_id == timer_id]

    def exists(self, swim_id: int, timer_id: int) -> bool:
        return any(a.swim_id == swim_id and a.timer_id == timer_id for a in self._by_id.values())


class InMemoryLapRepository:
    def __init__(self) -> None:
        self._items: list[Lap] = []
        self._seq = _Sequence()

    def add(self, lap: Lap) -> Lap:
        stored = replace(lap, id=lap.id or self._seq.next())
        self._items.append(stored)
        return stored

    def get_by_timer_swim_seq(self, timer_id: int, swim_id: int, seq: int) -> Lap | None:
        return next(
            (l for l in self._items if l.timer_id == timer_id and l.swim_id == swim_id and l.seq == seq),
            None,
        )

    def list_for_swim(self, swim_id: int) -> list[Lap]:
        return sorted((l for l in self._items if l.swim_id == swim_id), key=lambda l: l.seq)

    def highest_seq_for_swim(self, swim_id: int) -> int | None:
        seqs = [l.seq for l in self._items if l.swim_id == swim_id]
        return max(seqs) if seqs else None

    def last_valid_for_swim(self, swim_id: int) -> Lap | None:
        valid = [l for l in self._items if l.swim_id == swim_id and l.is_valid]
        return max(valid, key=lambda l: l.seq) if valid else None


class InMemoryReferenceLapRepository:
    def __init__(self) -> None:
        self._by_key: dict[tuple[int, int], ReferenceLap] = {}
        self._seq = _Sequence()

    def get(self, swim_id: int, lap_no: int) -> ReferenceLap | None:
        return self._by_key.get((swim_id, lap_no))

    def upsert(self, ref: ReferenceLap) -> ReferenceLap:
        key = (ref.swim_id, ref.lap_no)
        existing = self._by_key.get(key)
        stored = replace(ref, id=existing.id if existing else (ref.id or self._seq.next()))
        self._by_key[key] = stored
        return stored

    def list_for_swim(self, swim_id: int) -> list[ReferenceLap]:
        return sorted((r for r in self._by_key.values() if r.swim_id == swim_id), key=lambda r: r.lap_no)
