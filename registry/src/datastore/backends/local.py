import itertools
import json
from pathlib import Path
from typing import Any

from datastore.core import (
    atomic_write_json_file,
    compute_etag,
    construct_storage_path,
    extract_object_id_from_path,
    strip_id,
)
from datastore.exceptions import ConcurrencyError
from datastore.types import JsonDoc, PagedResult, ValueWithETag


class LocalBackend:
    """Local Filesystem based ObjectStore implementation.

    This backend adapts a local filesystem to the ObjectStore protocol. It manages
    two path concepts:
    - The logical "storage path", including the prefix (e.g., "prefix/accounts/acct-123.json").
      This is created by the `construct_storage_path` helper.
    - The physical "filesystem path", which is the absolute path on disk
      (e.g., "/tmp/data/prefix/accounts/acct-123.json").
    """

    def __init__(self, base_path: str, prefix: str = "") -> None:
        self.base_path = Path(base_path)
        self.prefix = prefix.strip("/")
        # Ensure the full root path for this backend exists.
        (self.base_path / self.prefix).mkdir(parents=True, exist_ok=True)

    def _get_fs_path(self, storage_path: str) -> Path:
        """Translates a logical storage path into a physical filesystem path."""
        return self.base_path.joinpath(storage_path)

    def get(self, object_id: str, *path_parts: str) -> ValueWithETag[JsonDoc]:
        """
        Retrieves a JSON object by its ID and path and returns (data, etag).
        """
        storage_path = construct_storage_path(prefix=self.prefix, path_parts=path_parts, object_id=object_id)
        file_path = self._get_fs_path(storage_path)
        if not file_path.exists():
            return None, None
        with file_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return raw, compute_etag(raw)

    def list(self, *path_parts: str, page: int = 1, per_page: int = 10) -> PagedResult[JsonDoc]:
        """
        Lists JSON objects from a specified path with pagination.
        The 'id' of each object is derived from its filename if not present in the file.
        """
        storage_dir = construct_storage_path(prefix=self.prefix, path_parts=path_parts)
        directory = self._get_fs_path(storage_dir)
        if not directory.exists():
            return []

        files = sorted([p for p in directory.iterdir() if p.suffix == ".json"], key=lambda p: p.stem)

        start = max(0, (page - 1) * per_page)
        page_files = itertools.islice(files, start, start + per_page)

        items: list[dict[str, Any]] = []
        for p in page_files:
            obj_id = extract_object_id_from_path(p.name)
            data, _ = self.get(obj_id, *path_parts)
            if data is None:
                continue
            data["id"] = obj_id
            items.append(data)
        return items

    def save(self, object_id: str, data: JsonDoc, *path_parts: str, if_match: str | None = None) -> None:
        """
        Saves a JSON object by its ID to a specified path.
        Keeps any explicit 'id' field provided by caller.
        If if_match is provided and the file exists, enforce optimistic concurrency using ETag.
        """
        storage_path = construct_storage_path(prefix=self.prefix, path_parts=path_parts, object_id=object_id)
        file_path = self._get_fs_path(storage_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # Concurrency: if_match must match existing ETag when updating; also skip write when unchanged
        current_etag: str | None = None
        if file_path.exists():
            with file_path.open("r", encoding="utf-8") as f:
                current = json.load(f)
            current_etag = compute_etag(current)
            if if_match is not None and if_match != current_etag:
                raise ConcurrencyError("ETag mismatch")
        # Never persist the 'id' field in the JSON content
        to_write = strip_id(data)
        # If content hash matches existing, no-op to avoid churn
        if current_etag is not None and compute_etag(to_write) == current_etag:
            return
        atomic_write_json_file(file_path, to_write)

    def delete(self, object_id: str, *path_parts: str) -> bool:
        """
        Deletes a JSON object by its ID from a specified path.
        Returns True if the object was deleted, False otherwise.
        """
        storage_path = construct_storage_path(prefix=self.prefix, path_parts=path_parts, object_id=object_id)
        file_path = self._get_fs_path(storage_path)
        if not file_path.exists():
            return False
        file_path.unlink()
        return True
