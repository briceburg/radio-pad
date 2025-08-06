from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable message")
    details: dict[str, Any] | None = Field(default=None, description="Optional structured details")


__all__ = ["ErrorDetail"]
