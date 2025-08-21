from datastore.core import ModelStore, ObjectStore
from models.station_preset import (
    AccountStationPreset,
    AccountStationPresetCreate,
    GlobalStationPreset,
    GlobalStationPresetCreate,
)


class GlobalPresets(ModelStore[GlobalStationPreset, GlobalStationPresetCreate]):
    """Repository for global station presets (presets/<id>.json)."""

    def __init__(self, backend: ObjectStore, create_model: type[GlobalStationPresetCreate]):
        super().__init__(backend, model=GlobalStationPreset, create_model=create_model, path_template="presets/{id}")


class AccountPresets(ModelStore[AccountStationPreset, AccountStationPresetCreate]):
    """Repository for account-scoped station presets (accounts/<account_id>/presets/<id>.json)."""

    def __init__(self, backend: ObjectStore, create_model: type[AccountStationPresetCreate]):
        super().__init__(
            backend,
            model=AccountStationPreset,
            create_model=create_model,
            path_template="accounts/{account_id}/presets/{id}",
        )
