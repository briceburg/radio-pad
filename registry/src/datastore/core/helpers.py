import hashlib
import json
import os
import tempfile
from pathlib import Path

from ..exceptions import ConcurrencyError
from ..types import JsonDoc


def canonical_json(data: JsonDoc) -> str:
    """Return a stable, canonical JSON string for hashing and comparisons.

    - Keys are sorted
    - No extra whitespace
    - UTF-8 friendly (ensure_ascii=False)
    """
    return json.dumps(data, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def storage_json(data: JsonDoc) -> str:
    """Return a stable, human-editable JSON string for persisted documents."""
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def compute_etag(data: JsonDoc) -> str:
    """Compute a SHA-256 hex digest over the canonical JSON representation."""
    payload = canonical_json(data).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def strip_id(data: JsonDoc) -> JsonDoc:
    """Return a shallow copy of the mapping without the 'id' field.

    Storage backends should not persist the 'id' inside the document body; the
    identifier is derived from the filename/object key.
    """
    return {k: v for k, v in data.items() if k != "id"}


def normalize_etag(token: str | None) -> str | None:
    """Strips leading/trailing quotes from an ETag string."""
    if token and token.startswith('"') and token.endswith('"'):
        return token[1:-1]
    return token


def validate_if_match(if_match: str | None, current_version: str | None) -> None:
    """Raise when a conditional-write token does not match the current version."""
    if if_match is not None and if_match != current_version:
        raise ConcurrencyError("ETag mismatch")


def extract_object_id_from_path(path: str) -> str:
    """Extracts the object ID from a storage path."""
    return Path(path).stem


def atomic_write_json_file(path: Path, data: JsonDoc) -> None:
    """Writes a JSON file atomically by writing to a temp file and then renaming."""
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f"{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as f:
            tmp_path = Path(f.name)
            f.write(storage_json(data))
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


def construct_storage_path(*, prefix: str, path_parts: tuple[str, ...], object_id: str | None = None) -> str:
    """Builds a backend storage path/key from components.

    - Ensures a trailing slash on the directory path if no object_id is provided.
    """
    parts = [p for p in path_parts if p]
    if prefix:
        parts.insert(0, prefix)
    if object_id:
        parts.append(f"{object_id}.json")
        return "/".join(parts)
    # Directory path
    if not parts:
        return ""
    dir_path = "/".join(parts)
    return dir_path if dir_path.endswith("/") else f"{dir_path}/"


def deconstruct_storage_path(full_key: str, *, prefix: str) -> tuple[str, tuple[str, ...]]:
    """Extracts the object ID and path parts from a full storage key."""
    key_path = Path(full_key)
    obj_id = key_path.stem
    path_parts_from_key = key_path.parent.parts
    if prefix:
        prefix_parts = prefix.split("/")
        path_parts_from_key = path_parts_from_key[len(prefix_parts) :]
    return obj_id, path_parts_from_key
