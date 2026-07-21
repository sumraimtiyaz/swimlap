"""Concrete security adapters (implement the service-layer ports).

Isolated here so the domain/services never import bcrypt or JWT directly. Swap
the algorithm or library and nothing above this file changes.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.domain.errors import DomainError, ErrorCode

# Unambiguous alphabet (no 0/O/1/l/I) — the coordinator reads the generated
# password aloud on a pool deck, so it must be transcribable.
_PW_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_password(groups: int = 3, group_len: int = 4) -> str:
    """A strong, human-transcribable one-time password like ``ABCD-EFGH-JKMN``."""
    parts = ["".join(secrets.choice(_PW_ALPHABET) for _ in range(group_len)) for _ in range(groups)]
    return "-".join(parts)


class BcryptPasswordHasher:
    _MAX_BYTES = 72

    def _encode(self, plain: str) -> bytes:
        return plain.encode("utf-8")[: self._MAX_BYTES]

    def hash(self, plain: str) -> str:
        return bcrypt.hashpw(self._encode(plain), bcrypt.gensalt()).decode("utf-8")

    def verify(self, plain: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(self._encode(plain), hashed.encode("utf-8"))
        except (ValueError, TypeError):
            return False


class JwtTokenProvider:
    def __init__(self, *, secret: str, algorithm: str, ttl_minutes: int):
        self._secret = secret
        self._algorithm = algorithm
        self._ttl = timedelta(minutes=ttl_minutes)

    def issue(self, *, subject: str, role: str) -> str:
        now = datetime.now(tz=timezone.utc)
        payload = {"sub": subject, "role": role, "iat": now, "exp": now + self._ttl}
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode(self, token: str) -> dict:
        try:
            return jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError as exc:
            raise DomainError(ErrorCode.AUTH_TOKEN_EXPIRED, "Session expired.") from exc
        except jwt.PyJWTError as exc:
            raise DomainError(ErrorCode.AUTH_TOKEN_EXPIRED, "Invalid token.") from exc
