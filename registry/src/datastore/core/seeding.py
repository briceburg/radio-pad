from __future__ import annotations

import re
from collections.abc import Mapping

from pydantic import BaseModel

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


def match_path_template(path: str, template: str) -> dict[str, str] | None:
    """Matches a path against a template, extracting placeholder values using regex.

    Returns a dictionary of extracted values if the path matches the template,
    otherwise returns None.
    """
    regex_pattern = _template_placeholder_re.sub(r"(?P<\1>[^/]+)", template)
    match = re.fullmatch(regex_pattern, path)
    return match.groupdict() if match else None


_template_placeholder_re = re.compile(r"\{([^}]+)\}")
