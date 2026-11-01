"""The uniform error envelope (docs/05_API_DESIGN.md §1).

``error_type`` is a closed, growing set shared between the API response body and
the operational log taxonomy (docs/13_OBSERVABILITY.md §4) -- one vocabulary,
two consumers, so failures can be clustered by grepping rather than parsing prose.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class OscarError(Exception):
    """Base for every domain error that must reach the client as a typed envelope."""

    error_type: str = "INTERNAL"
    status_code: int = 500

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


class UnauthorizedError(OscarError):
    error_type = "UNAUTHORIZED"
    status_code = 401


class NotFoundError(OscarError):
    error_type = "NOT_FOUND"
    status_code = 404


class IllegalTransitionError(OscarError):
    error_type = "ILLEGAL_TRANSITION"
    status_code = 409


class ConflictError(OscarError):
    error_type = "CONFLICT"
    status_code = 409


class ValidationFailedError(OscarError):
    """A well-formed request whose contents fail a domain rule (not a schema)."""

    error_type = "VALIDATION_FAILED"
    status_code = 422


class LLMUnavailableError(OscarError):
    error_type = "LLM_UNAVAILABLE"
    status_code = 503


class LLMRefusedError(OscarError):
    error_type = "LLM_REFUSED"
    status_code = 422


class GroundingFailedError(OscarError):
    """Every candidate bullet was rejected; no CV version is persisted (docs/07 §3)."""

    error_type = "GROUNDING_FAILED"
    status_code = 422


class StorageError(OscarError):
    error_type = "STORAGE_ERROR"
    status_code = 503


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(OscarError)
    async def _handle_oscar_error(_: Request, exc: OscarError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_type": exc.error_type,
                "message": exc.message,
                "detail": exc.detail,
            },
        )
