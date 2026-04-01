class ConcurrencyError(Exception):
    """Raised when conditional write preconditions fail (e.g., ETag mismatch)."""
