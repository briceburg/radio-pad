from __future__ import annotations

from collections.abc import Mapping
from string import Formatter

from pydantic import BaseModel

from ..exceptions import ConcurrencyError
from ..types import JsonDoc, PagedResult, PathParams
from .interfaces import ModelWithId, ObjectStore
from .seeding import match_path_template


class ModelStore[Entity: ModelWithId, Spec: BaseModel]:
    """Typed JSON resources backed by an ObjectStore.

    path_template must end with `{id}`, e.g. `accounts/{account_id}/players/{id}`.
    Other placeholders require path_params; save() can infer them from model fields.
    Path-derived identity is restored on reads and excluded from stored JSON.
    """

    def __init__(
        self,
        backend: ObjectStore,
        *,
        model: type[Entity],
        path_template: str,
    ):
        self._backend = backend
        self._model = model

        normalized = path_template.strip().strip("/")
        segments = [s for s in normalized.split("/") if s]
        if not segments:
            raise ValueError("path_template must not be empty")
        last = segments[-1]
        if last != "{id}":
            raise ValueError("path_template must end with '{id}'")
        self._path_template = f"{normalized}.json"
        self._dir_template = "/".join(segments[:-1])
        formatter = Formatter()
        req_keys: list[str] = []
        for _, field_name, _, _ in formatter.parse(self._dir_template):
            if field_name and field_name not in req_keys:
                if field_name == "id":
                    raise ValueError("'id' cannot appear in the directory portion of path_template")
                req_keys.append(field_name)
        self._required_keys: tuple[str, ...] = tuple(req_keys)
        self._reserved_keys: frozenset[str] = frozenset({"id", *self._required_keys})

    def match(self, path: str) -> dict[str, str] | None:
        return match_path_template(path.removesuffix(".json"), self._path_template.removesuffix(".json"))

    def seed(self, data: JsonDoc, *, path_params: PathParams | None = None) -> None:
        self.save(self._model.model_validate(data), path_params=path_params, if_none_match=True)

    def exists(self, object_id: str, *, path_params: PathParams | None = None) -> bool:
        """Load and validate the resource to check existence."""
        return self.get(object_id, path_params=path_params) is not None

    def get(self, object_id: str, *, path_params: PathParams | None = None) -> Entity | None:
        """Return a validated resource, or None when missing."""
        comps = self._dir_components(path_params=path_params)
        data, _ = self._backend.get(object_id, *comps)
        if data is None:
            return None
        payload = self._strip_reserved(data)
        base: dict[str, object] = {"id": object_id}
        if path_params:
            base.update({k: path_params[k] for k in self._required_keys})
        return self._model.model_validate({**base, **payload})

    def list(self, *, path_params: PathParams | None = None, page: int = 1, per_page: int = 10) -> PagedResult[Entity]:
        """Return a page of validated resources."""
        comps = self._dir_components(path_params=path_params)
        items = self._backend.list(*comps, page=page, per_page=per_page)

        param_vals = {k: path_params[k] for k in self._required_keys} if path_params else {}
        models: list[Entity] = []
        for item in items:
            file_id = item.get("id")
            payload = self._strip_reserved(item)
            base: dict[str, object] = {"id": file_id, **param_vals}
            models.append(self._model.model_validate({**base, **payload}))

        return models

    def upsert(self, object_id: str, spec: Spec, *, path_params: PathParams | None = None) -> Entity:
        """Replace or create a resource using a conditional write.

        Omitted optional fields take Spec defaults (PUT replacement semantics).
        Raises ConcurrencyError if storage changed since the initial read.
        """
        comps = self._dir_components(path_params=path_params)
        current, version = self._backend.get(object_id, *comps)
        base: dict[str, object] = {"id": object_id}
        if path_params:
            base.update({k: path_params[k] for k in self._required_keys})
        payload = self._strip_reserved(spec.model_dump(mode="json"))
        model = self._model.model_validate({**base, **payload})
        data = self._strip_reserved(model.model_dump(mode="json"))
        try:
            self._backend.save(
                model.id,
                data,
                *comps,
                if_match=version,
                if_none_match=current is None,
            )
        except ConcurrencyError as e:
            raise ConcurrencyError("Conditional save failed") from e
        return model

    def save(self, model_obj: Entity, *, path_params: PathParams | None = None, if_none_match: bool = False) -> Entity:
        """Persist a complete resource; infer path parameters from model fields when omitted."""
        if self._required_keys and path_params is None:
            path_params = self._path_params_from_model(model_obj)
        comps = self._dir_components(path_params=path_params)
        data = self._strip_reserved(model_obj.model_dump(mode="json"))
        self._backend.save(model_obj.id, data, *comps, if_none_match=if_none_match)
        return model_obj

    def _dir_components(self, *, path_params: PathParams | None = None) -> tuple[str, ...]:
        """Render path parameters, requiring every directory placeholder."""
        if not self._dir_template:
            return ()
        if self._required_keys and not path_params:
            raise ValueError("path_params is required for this repository")
        values = {k: path_params[k] for k in self._required_keys} if path_params else {}
        rendered = self._dir_template.format(**values)
        return tuple(c for c in rendered.split("/") if c)

    def _path_params_from_model(self, model_obj: Entity) -> PathParams:
        """Infer directory placeholders from same-named string fields on the model."""
        values: dict[str, str] = {}
        for key in self._required_keys:
            v = getattr(model_obj, key)
            if not isinstance(v, str):
                raise TypeError(f"path param field '{key}' must be str, got {type(v).__name__}")
            values[key] = v
        return values

    def _strip_reserved(self, mapping: Mapping[str, object]) -> dict[str, object]:
        """Remove the object ID and directory placeholders from a payload."""
        return {k: v for k, v in mapping.items() if k not in self._reserved_keys}
