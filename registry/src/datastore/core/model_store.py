from __future__ import annotations

from string import Formatter

from pydantic import BaseModel

from ..core import ObjectStore, match_path_template
from ..exceptions import ConcurrencyError
from ..types import JsonDoc, PagedResult, PathParams
from .interfaces import ModelWithId


class ModelStore[ReadModel: ModelWithId, CreateModel: BaseModel]:
    """
    Minimal, hierarchical repository backed by an ObjectStore (e.g., local fs, s3fs).

    path_template must end with the `{id}` placeholder.
    - Example: "accounts/{account_id}/presets/{id}"

    placeholders other than `{id}` in the path_template are passed as `path_params`.
    - Example: "accounts/{account_id}/presets/{id}", path_params={"account_id": "123"}

    Examples:
    - Flat collection:
      ModelStore(backend, model=Station, create_model=StationCreate, path_template="stations/{id}")

    - Account-scoped:
      ModelStore(backend, model=Preset, create_model=PresetCreate, path_template="accounts/{account_id}/presets/{id}")
      store.get("preset-1", path_params={"account_id": "acct-123"})

    Notes:
    - save() will infer path params from model fields if not provided.
    """

    def __init__(
        self,
        backend: ObjectStore,
        *,
        model: type[ReadModel],
        create_model: type[CreateModel],
        path_template: str,
    ):
        self._backend = backend
        self._model = model
        self._create_model = create_model
        # normalize and validate template
        normalized = path_template.strip().strip("/")
        segments = [s for s in normalized.split("/") if s]
        if not segments:
            raise ValueError("path_template must not be empty")
        last = segments[-1]
        if last != "{id}":
            raise ValueError("path_template must end with '{id}'")
        id_field = last[1:-1]
        if id_field != "id":
            raise ValueError("last placeholder must be '{id}'")
        self._path_template = f"{normalized}.json"
        # directory template excludes the final '{id}' segment
        self._dir_template = "/".join(segments[:-1])
        # collect required keys from the directory template
        formatter = Formatter()
        req_keys: list[str] = []
        for _, field_name, _, _ in formatter.parse(self._dir_template):
            if field_name and field_name not in req_keys:
                if field_name == "id":
                    raise ValueError("'id' cannot appear in the directory portion of path_template")
                req_keys.append(field_name)
        self._required_keys: tuple[str, ...] = tuple(req_keys)

    def match(self, path: str) -> dict[str, str] | None:
        """Matches a path against the store's template, extracting params."""
        path_stem = path.removesuffix(".json")
        template_stem = self._path_template.removesuffix(".json")
        return match_path_template(path_stem, template_stem)

    @property
    def _reserved_keys(self) -> set[str]:
        return {"id", *self._required_keys}

    def _dir_components(self, *, path_params: PathParams | None = None) -> tuple[str, ...]:
        if not self._dir_template:
            return ()
        if self._required_keys and not path_params:
            raise ValueError("path_params is required for this repository")
        values = {k: path_params[k] for k in self._required_keys} if path_params else {}
        rendered = self._dir_template.format(**values)
        return tuple(c for c in rendered.split("/") if c)

    def _path_params_from_model(self, model_obj: ReadModel) -> PathParams:
        values: dict[str, str] = {}
        for key in self._required_keys:
            # We can't use hasattr here because ReadModel is a protocol.
            # Instead, we'll just try to access the attribute and let it raise.
            v = getattr(model_obj, key)
            if not isinstance(v, str):
                raise TypeError(f"path param field '{key}' must be str, got {type(v).__name__}")
            values[key] = v
        return values

    def get(self, object_id: str, *, path_params: PathParams | None = None) -> ReadModel | None:
        comps = self._dir_components(path_params=path_params)
        data, _ = self._backend.get(object_id, *comps)
        if data is None:
            return None
        reserved = self._reserved_keys
        payload = {k: v for k, v in data.items() if k not in reserved}
        base: dict[str, object] = {"id": object_id}
        if path_params:
            base.update({k: path_params[k] for k in self._required_keys})
        return self._model.model_validate({**base, **payload})

    def list(
        self, *, path_params: PathParams | None = None, page: int = 1, per_page: int = 10
    ) -> PagedResult[ReadModel]:
        comps = self._dir_components(path_params=path_params)
        items = self._backend.list(*comps, page=page, per_page=per_page)

        param_vals = {k: path_params[k] for k in self._required_keys} if path_params else {}
        reserved = self._reserved_keys
        models: list[ReadModel] = []
        for item in items:
            file_id = item.get("id")
            payload = {k: v for k, v in item.items() if k not in reserved}
            base: dict[str, object] = {"id": file_id, **param_vals}
            models.append(self._model.model_validate({**base, **payload}))

        return models

    def save(self, model_obj: ReadModel, *, path_params: PathParams | None = None) -> ReadModel:
        if self._required_keys and path_params is None:
            path_params = self._path_params_from_model(model_obj)
        comps = self._dir_components(path_params=path_params)
        reserved = self._reserved_keys
        data = {k: v for k, v in model_obj.model_dump(mode="json").items() if k not in reserved}
        self._backend.save(model_obj.id, data, *comps)
        return model_obj

    def merge_upsert(self, object_id: str, partial: CreateModel, *, path_params: PathParams | None = None) -> ReadModel:
        comps = self._dir_components(path_params=path_params)
        current, version = self._backend.get(object_id, *comps)
        base: dict[str, object] = {"id": object_id}
        if path_params:
            base.update({k: path_params[k] for k in self._required_keys})
        merged = {
            **({} if current is None else current),
            **partial.model_dump(exclude_unset=True),
        }
        reserved = self._reserved_keys
        payload = {k: v for k, v in merged.items() if k not in reserved}
        model = self._model.model_validate({**base, **payload})
        data = {k: v for k, v in model.model_dump(mode="json").items() if k not in reserved}
        try:
            self._backend.save(model.id, data, *comps, if_match=version if current is not None else None)
        except ConcurrencyError as e:  # backend conflict (e.g., ETag mismatch)
            raise ConcurrencyError("Conditional save failed") from e
        return model

    def seed(self, data: JsonDoc, *, path_params: PathParams | None = None) -> None:
        """Create or overwrite a model instance from seed data in one call."""
        model = self._model.model_validate(data)
        self.save(model, path_params=path_params)

    # --- Additional convenience operations ---
    def exists(self, object_id: str, *, path_params: PathParams | None = None) -> bool:
        return self.get(object_id, path_params=path_params) is not None

    def delete(self, object_id: str, *, path_params: PathParams | None = None) -> bool:
        comps = self._dir_components(path_params=path_params)
        return self._backend.delete(object_id, *comps)
