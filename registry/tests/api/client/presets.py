from starlette.testclient import TestClient

from api.models.pagination import PaginationParams
from datastore.types import JsonDoc
from models.station_preset import AccountStationPresetCreate, GlobalStationPresetCreate
from tests.api._helpers import get_json, put_json


class PresetApi:
    def __init__(self, client: TestClient):
        self._client = client

    def put_global(self, preset_id: str, payload: GlobalStationPresetCreate, expected_status: int = 200) -> JsonDoc:
        return put_json(
            self._client,
            f"/v1/presets/{preset_id}",
            payload,
            expected=expected_status,
        )

    def get_global(self, preset_id: str, expected_status: int = 200) -> JsonDoc:
        return get_json(
            self._client,
            f"/v1/presets/{preset_id}",
            expected=expected_status,
        )

    def list_global(self, expected_status: int = 200, params: PaginationParams | None = None) -> JsonDoc:
        return get_json(
            self._client,
            "/v1/presets",
            expected=expected_status,
            params=params,
        )

    def put_account(
        self, account_id: str, preset_id: str, payload: AccountStationPresetCreate, expected_status: int = 200
    ) -> JsonDoc:
        return put_json(
            self._client,
            f"/v1/accounts/{account_id}/presets/{preset_id}",
            payload,
            expected=expected_status,
        )

    def get_account(self, account_id: str, preset_id: str, expected_status: int = 200) -> JsonDoc:
        return get_json(
            self._client,
            f"/v1/accounts/{account_id}/presets/{preset_id}",
            expected=expected_status,
        )

    def list_account(
        self, account_id: str, expected_status: int = 200, params: PaginationParams | None = None
    ) -> JsonDoc:
        return get_json(
            self._client,
            f"/v1/accounts/{account_id}/presets",
            expected=expected_status,
            params=params,
        )
