from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel

from lib.logging import logger

from ..types import JsonDoc, PathParams
from .interfaces import ModelWithId, SeedableStore
from .model_store import ModelStore


class _SeedingView[Entity: ModelWithId, Create: BaseModel](SeedableStore):
    """Adapter exposing only the seeding-related surface for a ModelStore.

    This keeps seeding concerns out of the main ModelStore's public API.
    """

    def __init__(self, store: ModelStore[Entity, Create]) -> None:
        self._store = store

    def match(self, path: str) -> dict[str, str] | None:
        # Derive stems to avoid duplicated ".json" suffixes
        path_stem = path.removesuffix(".json")
        template_stem = self._store._path_template.removesuffix(".json")
        return match_path_template(path_stem, template_stem)

    def exists(self, object_id: str, *, path_params: Mapping[str, str] | None = None) -> bool:
        return self._store.get(object_id, path_params=path_params) is not None

    def seed(self, data: JsonDoc, *, path_params: PathParams | None = None) -> None:
        # Validate and save via underlying store; mirrors previous ModelStore.seed
        model = self._store._model.model_validate(data)
        self._store.save(model, path_params=path_params)


def seedable[Entity: ModelWithId, Create: BaseModel](
    store: ModelStore[Entity, Create],
) -> SeedableStore:
    """Return a SeedableStore view for the given ModelStore."""
    return _SeedingView(store)


def seed_from_path(seed_path: Path, stores: list[SeedableStore], *, label: str) -> None:
    if not seed_path.is_dir():
        logger.error("%s seed path does not exist: %s", label, seed_path)
        return

    for seed_file in seed_path.rglob("*.json"):
        relative_path = seed_file.relative_to(seed_path).as_posix()

        for store in stores:
            if not (params := store.match(relative_path)):
                continue

            object_id = params.pop("id")
            path_params = params or None
            if store.exists(object_id, path_params=path_params):
                logger.debug("Skipping existing %s object: %s", label, relative_path)
                break

            with seed_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            store.seed({"id": object_id, **params, **data}, path_params=path_params)
            logger.info("Seeded %s %s", label, relative_path)
            break


def match_path_template(path: str, template: str) -> dict[str, str] | None:
    """Matches a path against a template, extracting placeholder values using regex.

    Returns a dictionary of extracted values if the path matches the template,
    otherwise returns None.
    """
    regex_pattern = _template_placeholder_re.sub(r"(?P<\1>[^/]+)", template)
    match = re.fullmatch(regex_pattern, path)
    return match.groupdict() if match else None


_template_placeholder_re = re.compile(r"\{([^}]+)\}")
