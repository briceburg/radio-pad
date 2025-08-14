import json
import os
from pathlib import Path
from typing import Any

from datastore.core import compute_etag, strip_id
from datastore.types import JsonDoc, PagedResult, ValueWithETag


class LocalBackend:
    """Local Filesystem based ObjectStore implementation."""

    def __init__(self, base_path: str) -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_path(self, *parts: str) -> Path:
        """Constructs a path relative to the base path."""
        return self.base_path.joinpath(*parts)

    def _etag_for(self, data: dict[str, Any]) -> str:
        return compute_etag(data)

    def get(self, object_id: str, *path_parts: str) -> ValueWithETag[JsonDoc]:
        """
        Retrieves a JSON object by its ID from a specified path and returns (data, version).
        """
        file_path = self._get_path(*path_parts, f"{object_id}.json")
        if not file_path.exists():
            return None, None
        with file_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        etag = self._etag_for(raw)
        return raw, etag

    def list(self, *path_parts: str, page: int = 1, per_page: int = 10) -> PagedResult[JsonDoc]:
        """
        Lists JSON objects from a specified path with pagination.
        The 'id' of each object is derived from its filename if not present in the file.
        """
        directory = self._get_path(*path_parts)
        if not directory.exists():
            return [], 0
        files = sorted([p for p in directory.iterdir() if p.suffix == ".json"], key=lambda p: p.stem)
        total = len(files)
        start = max(0, (page - 1) * per_page)
        end = start + per_page
        items: list[dict[str, Any]] = []
        for p in files[start:end]:
            with p.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            raw["id"] = p.stem
            items.append(raw)
        return items, total

    def save(self, object_id: str, data: JsonDoc, *path_parts: str, if_match: str | None = None) -> None:
        """
        Saves a JSON object by its ID to a specified path.
        Keeps any explicit 'id' field provided by caller.
        If if_match is provided and the file exists, enforce optimistic concurrency using ETag.
        """
        file_path = self._get_path(*path_parts, f"{object_id}.json")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # Concurrency: if_match must match existing ETag when updating; also skip write when unchanged
        current_etag: str | None = None
        if file_path.exists():
            with file_path.open("r", encoding="utf-8") as f:
                current = json.load(f)
            current_etag = self._etag_for(current)
            if if_match is not None and if_match != current_etag:
                raise ValueError("ETag mismatch")
        # Never persist the 'id' field in the JSON content
        to_write = strip_id(data)
        # If content hash matches existing, no-op to avoid churn
        if current_etag is not None and self._etag_for(to_write) == current_etag:
            return None
        tmp_path = file_path.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(to_write, f, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
        os.replace(tmp_path, file_path)

    def delete(self, object_id: str, *path_parts: str) -> bool:
        """
        Deletes a JSON object by its ID from a specified path.
        Returns True if the object was deleted, False otherwise.
        """
        file_path = self._get_path(*path_parts, f"{object_id}.json")
        if not file_path.exists():
            return False
        file_path.unlink()
        return True
