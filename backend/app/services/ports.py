"""Infrastructure ports used by services.

These abstract away *how* passwords are hashed, tokens are signed, and time is
read. Services depend on the Protocol; production wires in bcrypt/JWT/system
clock; tests wire in trivial fakes. Nothing in the service layer imports a crypto
or time library directly (SRP + DIP).
"""
from __future__ import annotations

from typing import Protocol


class PasswordHasher(Protocol):
    def hash(self, plain: str) -> str: ...
    def verify(self, plain: str, hashed: str) -> bool: ...


class TokenProvider(Protocol):
    def issue(self, *, subject: str, role: str) -> str: ...
    def decode(self, token: str) -> dict: ...  # raises DomainError(AUTH_TOKEN_EXPIRED) on failure


class Clock(Protocol):
    def now_ms(self) -> float:
        """Server wall-clock time in ms since the Unix epoch (chrony-disciplined)."""

    def now(self):  # -> datetime
        """Server wall-clock as a timezone-aware datetime."""
