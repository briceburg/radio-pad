from __future__ import annotations

from typing import Any


class ApiError(Exception):
    def __init__(self, message: str, *, code: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


class NotFoundError(ApiError):
    def __init__(self, message: str = "Resource not found", *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="not_found", details=details)


__all__ = ["ApiError", "NotFoundError"]
