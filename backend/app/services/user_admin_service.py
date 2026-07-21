"""Coordinator-only account administration.

Accounts are *issued, never self-created* (PRD §4). The system generates the
password; the plaintext is returned exactly once (in the create/reset response)
and then only the bcrypt hash survives. Password reset and deactivation both
stamp ``tokens_valid_from = now`` so every live token for that account dies
immediately — no session store required.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.security import generate_password
from app.domain.entities import User
from app.domain.enums import UserRole
from app.domain.errors import DomainError, ErrorCode
from app.repositories.interfaces import UserRepository
from app.services.ports import Clock, PasswordHasher


@dataclass(frozen=True)
class IssuedAccount:
    user: User
    password: str  # plaintext — surfaced once, never stored


class UserAdminService:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, clock: Clock):
        self._users = users
        self._hasher = hasher
        self._clock = clock

    def create_user(self, *, username: str, display_name: str, role: UserRole = UserRole.TIMER) -> IssuedAccount:
        username = username.strip().lower()
        if not username:
            raise DomainError(ErrorCode.VALIDATION_ERROR, "A login id is required.")
        if self._users.get_by_username(username) is not None:
            raise DomainError(ErrorCode.VALIDATION_ERROR, "That login id is already in use.")
        password = generate_password()
        stored = self._users.add(User(
            id=0, username=username, display_name=display_name.strip(), role=role,
            hashed_password=self._hasher.hash(password), is_active=True,
            created_at=self._clock.now(), tokens_valid_from=None,
        ))
        return IssuedAccount(user=stored, password=password)

    def reset_password(self, user_id: int) -> IssuedAccount:
        user = self._require(user_id)
        password = generate_password()
        user.hashed_password = self._hasher.hash(password)
        user.tokens_valid_from = self._clock.now()  # kill every live token
        return IssuedAccount(user=self._users.update(user), password=password)

    def deactivate(self, user_id: int) -> User:
        user = self._require(user_id)
        user.is_active = False
        user.tokens_valid_from = self._clock.now()  # kill every live token
        return self._users.update(user)

    def list_users(self, role: UserRole | None = None) -> list[User]:
        users = self._users.list_all()
        return [u for u in users if role is None or u.role is role]

    def _require(self, user_id: int) -> User:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise DomainError(ErrorCode.USER_NOT_FOUND, "User does not exist.")
        return user
