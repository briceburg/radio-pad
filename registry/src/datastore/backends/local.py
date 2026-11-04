import itertools
import json
from pathlib import Path
from typing import Any

from datastore.core import (
    InterProcessLock,
    atomic_write_json_file,
    compute_etag,
    construct_storage_path,
    extract_object_id_from_path,
    strip_id,
    validate_write_preconditions,
)
from datastore.types import JsonDoc, PagedResult, ValueWithETag


class LocalBackend:
    """Filesystem-backed ObjectStore with atomic, conditionally locked writes."""

    def __init__(self, base_path: str, prefix: str = "") -> None:
        self.base_path = Path(base_path)
        self.prefix = prefix.strip("/")
        (self.base_path / self.prefix).mkdir(parents=True, exist_ok=True)
        self._write_lock = InterProcessLock(self.base_path / ".write.lock")

    def _get_fs_path(self, storage_path: str) -> Path:
        """Translate a logical storage path to a filesystem path."""
        return self.base_path.joinpath(storage_path)

    def _read(self, file_path: Path) -> ValueWithETag[JsonDoc]:
        try:
            with file_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except FileNotFoundError:
            return None, None
        return raw, compute_etag(raw)

    def get(self, object_id: str, *path_parts: str) -> ValueWithETag[JsonDoc]:
        """Retrieve a JSON object and its content ETag."""
        storage_path = construct_storage_path(prefix=self.prefix, path_parts=path_parts, object_id=object_id)
        return self._read(self._get_fs_path(storage_path))

    def list(self, *path_parts: str, page: int = 1, per_page: int = 10) -> PagedResult[JsonDoc]:
        """List JSON objects, deriving each ID from its filename."""
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

    def save(
        self,
        object_id: str,
        data: JsonDoc,
        *path_parts: str,
        if_match: str | None = None,
        if_none_match: bool = False,
    ) -> None:
        """Persist an object after atomically validating its write preconditions."""
        storage_path = construct_storage_path(prefix=self.prefix, path_parts=path_parts, object_id=object_id)
        file_path = self._get_fs_path(storage_path)
        with self._write_lock():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            _, current_etag = self._read(file_path)
            validate_write_preconditions(if_match, if_none_match, current_etag)
            to_write = strip_id(data)
            if compute_etag(to_write) == current_etag:
                return
            atomic_write_json_file(file_path, to_write, overwrite=not if_none_match)

    def delete(self, object_id: str, *path_parts: str) -> bool:
        """Delete an object and report whether it existed."""
        storage_path = construct_storage_path(prefix=self.prefix, path_parts=path_parts, object_id=object_id)
        file_path = self._get_fs_path(storage_path)
        with self._write_lock():
            try:
                file_path.unlink()
                return True
            except FileNotFoundError:
                return False
