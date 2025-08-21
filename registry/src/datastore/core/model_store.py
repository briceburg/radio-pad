from __future__ import annotations

from collections.abc import Mapping
from string import Formatter

from pydantic import BaseModel

from ..core import ObjectStore
from ..exceptions import ConcurrencyError
from ..types import PagedResult, PathParams
from .interfaces import ModelWithId


class ModelStore[Entity: ModelWithId, Create: BaseModel]:
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
        model: type[Entity],
        create_model: type[Create],
        path_template: str,
    ):
        """Initialize a ModelStore.

        Args:
            backend: Object storage backend used for persistence.
            model: Concrete model type
            create_model: Input model type used for create/merge operations.
            path_template: Hierarchical JSON path template ending with "{id}".
        """
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
        self._reserved_keys: frozenset[str] = frozenset({"id", *self._required_keys})

    def delete(self, object_id: str, *, path_params: PathParams | None = None) -> bool:
        """Delete a model by id

        Returns:
            True if an object was deleted, False if it did not exist.
        """
        comps = self._dir_components(path_params=path_params)
        return self._backend.delete(object_id, *comps)

    def exists(self, object_id: str, *, path_params: PathParams | None = None) -> bool:
        """Return True if a model with the given id exists; otherwise False."""
        return self.get(object_id, path_params=path_params) is not None

    def get(self, object_id: str, *, path_params: PathParams | None = None) -> Entity | None:
        """Fetch a single model by id.
        Returns:
            The validated model instance, or None if it does not exist.
        """
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
        """List models under the path, paginated.
        Returns:
            A list of validated model instances.
        """
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

    def merge_upsert(self, object_id: str, partial: Create, *, path_params: PathParams | None = None) -> Entity:
        """Merge a partial payload and upsert with OCC.

        If the object exists, merges the provided partial into current data and
        performs a conditional save using the backend version (ETag). If it does not
        exist, creates the object.

        This is used by PUT methods in the API.

        Raises:
            ConcurrencyError: If a conditional save fails due to a version conflict.

        Returns:
            The validated, persisted model instance.
        """
        comps = self._dir_components(path_params=path_params)
        current, version = self._backend.get(object_id, *comps)
        base: dict[str, object] = {"id": object_id}
        if path_params:
            base.update({k: path_params[k] for k in self._required_keys})
        merged = {
            **({} if current is None else current),
            **partial.model_dump(exclude_unset=True),
        }
        payload = self._strip_reserved(merged)
        model = self._model.model_validate({**base, **payload})
        data = self._strip_reserved(model.model_dump(mode="json"))
        try:
            self._backend.save(model.id, data, *comps, if_match=version if current is not None else None)
        except ConcurrencyError as e:  # backend conflict (e.g., ETag mismatch)
            raise ConcurrencyError("Conditional save failed") from e
        return model

    def save(self, model_obj: Entity, *, path_params: PathParams | None = None) -> Entity:
        """Persist a complete model

        If required path parameters are not provided, this method attempts to
        infer them from identically named string fields on the model.

        Returns:
            The saved model (same instance).
        """
        if self._required_keys and path_params is None:
            path_params = self._path_params_from_model(model_obj)
        comps = self._dir_components(path_params=path_params)
        data = self._strip_reserved(model_obj.model_dump(mode="json"))
        self._backend.save(model_obj.id, data, *comps)
        return model_obj

    def _dir_components(self, *, path_params: PathParams | None = None) -> tuple[str, ...]:
        """Render the directory portion of the path into components.

        Raises:
            ValueError: If required path parameters are missing.

        Returns:
            A tuple of components to prefix before the object id.
        """
        if not self._dir_template:
            return ()
        if self._required_keys and not path_params:
            raise ValueError("path_params is required for this repository")
        values = {k: path_params[k] for k in self._required_keys} if path_params else {}
        rendered = self._dir_template.format(**values)
        return tuple(c for c in rendered.split("/") if c)

    def _path_params_from_model(self, model_obj: Entity) -> PathParams:
        """Extract required path parameters from a model instance.

        Each required key must exist on the model and be of type str.
        """
        values: dict[str, str] = {}
        for key in self._required_keys:
            v = getattr(model_obj, key)
            if not isinstance(v, str):
                raise TypeError(f"path param field '{key}' must be str, got {type(v).__name__}")
            values[key] = v
        return values

    def _strip_reserved(self, mapping: Mapping[str, object]) -> dict[str, object]:
        """Return a shallow copy of mapping without reserved keys.

        Reserved keys include the object id and any required directory placeholders.
        """
        return {k: v for k, v in mapping.items() if k not in self._reserved_keys}
