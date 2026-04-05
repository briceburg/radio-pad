from http import HTTPStatus

import pytest
from starlette.testclient import TestClient

from datastore.types import JsonDoc
from models.station_preset import AccountStationPresetCreate, GlobalStationPresetCreate
from tests.api._helpers import assert_item_fields, assert_paginated
from tests.api.client.presets import PresetApi


class TestGlobalPresets:
    def test_list_global_presets(self, preset_api: PresetApi) -> None:
        data = preset_api.list_global()
        assert_paginated(data)

    def test_get_global_preset(self, preset_api: PresetApi) -> None:
        preset_id = "test-preset"
        preset_api.put_global(
            preset_id,
            GlobalStationPresetCreate.model_validate(
                {"name": "Test Preset", "stations": [{"name": "A", "url": "https://a.com"}]}
            ),
        )
        data = preset_api.get_global(preset_id)
        assert data["id"] == preset_id
        assert isinstance(data["stations"], list)

    def test_register_global_preset_full_payload(self, preset_api: PresetApi) -> None:
        preset_id = "new-global-preset"
        payload = GlobalStationPresetCreate.model_validate(
            {
                "name": "New Global Preset",
                "category": "News",
                "description": "A collection of news stations.",
                "stations": [{"name": "A Cool Station", "url": "https://cool.station/stream"}],
            }
        )
        data = preset_api.put_global(preset_id, payload)
        assert_item_fields(
            data,
            id=preset_id,
            name=payload.name,
            category=payload.category,
            description=payload.description,
        )
        assert "account_id" not in data


class TestAccountPresets:
    ACCOUNT_ID = "testuser"

    @pytest.mark.parametrize(
        "preset_id,payload",
        [
            (
                "my-preset",
                AccountStationPresetCreate.model_validate(
                    {"name": "My Preset", "stations": [{"name": "A", "url": "https://a.com"}]}
                ),
            ),
            (
                "my-custom-preset",
                AccountStationPresetCreate.model_validate(
                    {
                        "name": "My Custom Preset",
                        "category": "Personal",
                        "description": "My personal list of stations.",
                        "stations": [{"name": "A Cool Station", "url": "https://cool.station/stream"}],
                    }
                ),
            ),
        ],
    )
    def test_account_preset_create_and_get(
        self, preset_api: PresetApi, preset_id: str, payload: AccountStationPresetCreate
    ) -> None:
        put_data = preset_api.put_account(self.ACCOUNT_ID, preset_id, payload)
        assert_item_fields(put_data, id=preset_id, account_id=self.ACCOUNT_ID, name=payload.name)

        get_data = preset_api.get_account(self.ACCOUNT_ID, preset_id)
        assert_item_fields(get_data, id=preset_id, account_id=self.ACCOUNT_ID)

    def test_list_account_presets(self, preset_api: PresetApi) -> None:
        preset_api.put_account(
            self.ACCOUNT_ID,
            "list-one",
            AccountStationPresetCreate.model_validate(
                {"name": "List One", "stations": [{"name": "A", "url": "https://a.com"}]}
            ),
        )
        data = preset_api.list_account(self.ACCOUNT_ID)
        assert_paginated(data)
        assert len(data["items"]) == 1
        first = data["items"][0]
        assert_item_fields(first, id="list-one", account_id=self.ACCOUNT_ID)


# -------------------- Validation (Success & Failure) --------------------
@pytest.mark.parametrize(
    "url_template,body",
    [
        ("presets/{preset_id}", {"stations": []}),  # missing name
        ("presets/{preset_id}", {"name": "No Stations"}),  # missing stations
        ("accounts/testuser/presets/{preset_id}", {"stations": []}),
        ("accounts/testuser/presets/{preset_id}", {"name": "No Stations"}),
    ],
)
def test_preset_create_validation_failures(
    client: TestClient, url_template: str, body: GlobalStationPresetCreate | AccountStationPresetCreate | JsonDoc
) -> None:
    preset_id = "invalid"
    payload = body if isinstance(body, dict) else body.model_dump(exclude_none=True)
    resp = client.put(url_template.format(preset_id=preset_id), json=payload)
    assert resp.status_code == 422
    assert resp.json()["detail"]


def test_preset_rejects_duplicate_station_names(client: TestClient) -> None:
    payload = {
        "name": "Dup Names",
        "stations": [
            {"name": "Same", "url": "https://a.example/stream"},
            {"name": "same", "url": "https://b.example/stream"},
        ],
    }
    resp = client.put("presets/dup-names", json=payload)
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    body = resp.json()
    assert any("Duplicate station name" in (err.get("msg") or str(err)) for err in body.get("detail", []))


def test_preset_rejects_duplicate_station_urls(client: TestClient) -> None:
    payload = {
        "name": "Dup URLs",
        "stations": [
            {"name": "A", "url": "https://same.example/stream"},
            {"name": "B", "url": "https://same.example/stream"},
        ],
    }
    resp = client.put("presets/dup-urls", json=payload)
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    body = resp.json()
    assert any("Duplicate station URL" in (err.get("msg") or str(err)) for err in body.get("detail", []))
