"""Translate ``DomainError`` codes into HTTP responses.

This is the *only* place business errors meet HTTP. Services stay transport-free;
the mapping lives here so a new error code is a one-line change and the client
always receives ``{code, message, details}``.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.errors import DomainError, ErrorCode

_STATUS: dict[str, int] = {
    ErrorCode.AUTH_INVALID_CREDENTIALS: 401,
    ErrorCode.AUTH_TOKEN_EXPIRED: 401,
    ErrorCode.AUTH_ACCOUNT_DISABLED: 401,
    ErrorCode.AUTH_LOCKED: 429,
    ErrorCode.FORBIDDEN_ROLE: 403,
    ErrorCode.NOT_OWNER: 403,
    ErrorCode.NOT_ASSIGNED: 403,
    ErrorCode.USER_NOT_FOUND: 404,
    ErrorCode.SWIM_NOT_FOUND: 404,
    ErrorCode.SWIM_NOT_LIVE: 409,
    ErrorCode.ILLEGAL_STATE_TRANSITION: 409,
    ErrorCode.LAP_DUPLICATE_SEQ: 409,
    ErrorCode.OVERLAPPING_ASSIGNMENT: 409,
    ErrorCode.LAP_INVALID_TIMING: 422,
    ErrorCode.VALIDATION_ERROR: 400,
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        status = _STATUS.get(exc.code, 400)
        return JSONResponse(
            status_code=status,
            content={"code": exc.code, "message": exc.message, "details": exc.details},
        )
