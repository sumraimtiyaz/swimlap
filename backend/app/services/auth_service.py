"""Authentication service.

Verifies credentials and issues tokens. Depends only on ``UserRepository``,
``PasswordHasher``, ``TokenProvider`` and a ``LoginThrottle`` — so it can be
tested with fakes and would work unchanged behind any transport.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities import User
from app.domain.errors import DomainError, ErrorCode
from app.repositories.interfaces import UserRepository
from app.services.login_throttle import LoginThrottle
from app.services.ports import PasswordHasher, TokenProvider


@dataclass(frozen=True)
class AuthResult:
    token: str
    user: User


class AuthService:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, tokens: TokenProvider, throttle: LoginThrottle):
        self._users = users
        self._hasher = hasher
        self._tokens = tokens
        self._throttle = throttle

    def login(self, username: str, password: str) -> AuthResult:
        username = username.strip().lower()
        self._throttle.check(username)  # raises AUTH_LOCKED while blocked

        user = self._users.get_by_username(username)
        # Verify against a real-looking hash even when the user is missing to keep
        # the timing of both branches similar (mitigates user-enumeration).
        placeholder = "$fake$never$matches"
        candidate_hash = user.hashed_password if user else placeholder
        password_ok = self._hasher.verify(password, candidate_hash)

        if user is None or not password_ok:
            self._throttle.record_failure(username)
            raise DomainError(ErrorCode.AUTH_INVALID_CREDENTIALS, "Login id or password is incorrect.")

        # Credentials are valid; a wrong password never reached here. A disabled
        # account is told so (PRD §6.1) and does not count against the throttle.
        if not user.is_active:
            raise DomainError(ErrorCode.AUTH_ACCOUNT_DISABLED,
                              "This account has been deactivated. Contact your coordinator.")

        self._throttle.record_success(username)
        token = self._tokens.issue(subject=str(user.id), role=user.role.value)
        return AuthResult(token=token, user=user)
