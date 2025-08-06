from datastore.core import ModelStore, ObjectStore
from models.station_preset import AccountStationPreset, GlobalStationPreset


class GlobalPresets(ModelStore[GlobalStationPreset]):
    """Repository for global station presets (presets/<id>.json)."""

    def __init__(self, backend: ObjectStore):
        super().__init__(backend, model=GlobalStationPreset, path_template="presets/{id}")


class AccountPresets(ModelStore[AccountStationPreset]):
    """Repository for account-scoped station presets (accounts/<account_id>/presets/<id>.json)."""

    def __init__(self, backend: ObjectStore):
        super().__init__(
            backend,
            model=AccountStationPreset,
            path_template="accounts/{account_id}/presets/{id}",
        )
