"""Framework-agnostic domain errors.

Services raise ``DomainError`` with a stable ``code`` from the shared contract.
The API layer (and only the API layer) maps codes to HTTP status. Keeping this
out of the domain means the same services could power a CLI, a gRPC endpoint, or
a background worker without dragging HTTP concepts along (SRP / DIP).
"""
from __future__ import annotations


class ErrorCode:
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_LOCKED = "AUTH_LOCKED"
    AUTH_ACCOUNT_DISABLED = "AUTH_ACCOUNT_DISABLED"
    FORBIDDEN_ROLE = "FORBIDDEN_ROLE"
    NOT_OWNER = "NOT_OWNER"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    SWIM_NOT_FOUND = "SWIM_NOT_FOUND"
    SWIM_NOT_LIVE = "SWIM_NOT_LIVE"
    NOT_ASSIGNED = "NOT_ASSIGNED"
    OVERLAPPING_ASSIGNMENT = "OVERLAPPING_ASSIGNMENT"
    LAP_INVALID_TIMING = "LAP_INVALID_TIMING"
    LAP_DUPLICATE_SEQ = "LAP_DUPLICATE_SEQ"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    ILLEGAL_STATE_TRANSITION = "ILLEGAL_STATE_TRANSITION"


class DomainError(Exception):
    """An expected, business-rule violation (not a bug).

    ``code`` is a stable machine-readable identifier; ``message`` is a
    human-readable default; ``details`` carries optional structured context.
    """

    def __init__(self, code: str, message: str = "", details: dict | None = None):
        self.code = code
        self.message = message or code
        self.details = details or {}
        super().__init__(f"{code}: {self.message}")
