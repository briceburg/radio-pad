import hashlib
import json
from typing import Any

# TODO: bake these into the model_store?


def canonical_json(data: dict[str, Any]) -> str:
    """Return a stable, canonical JSON string for hashing and comparisons.

    - Keys are sorted
    - No extra whitespace
    - UTF-8 friendly (ensure_ascii=False)
    """
    return json.dumps(data, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def compute_etag(data: dict[str, Any]) -> str:
    """Compute a SHA-256 hex digest over the canonical JSON representation."""
    payload = canonical_json(data).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def strip_id(data: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of the mapping without the 'id' field.

    Storage backends should not persist the 'id' inside the document body; the
    identifier is derived from the filename/object key.
    """
    return {k: v for k, v in data.items() if k != "id"}
