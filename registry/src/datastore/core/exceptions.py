from __future__ import annotations


class ConcurrencyError(Exception):
    """Raised when conditional write preconditions fail (e.g., ETag mismatch)."""


__all__ = ["ConcurrencyError"]
