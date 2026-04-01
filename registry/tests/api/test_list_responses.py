"""Tests to ensure list endpoints return abbreviated summary models, not full models."""

from datastore.types import JsonDoc
from models.account import AccountCreate
from models.player import PlayerCreate
from models.station_preset import AccountStationPresetCreate, GlobalStationPresetCreate
from tests.api._helpers import assert_exact_fields, find_item
from tests.api.client.accounts import AccountApi
from tests.api.client.players import PlayerApi
from tests.api.client.presets import PresetApi


def _assert_summary_item(item: JsonDoc, *expected_fields: str) -> None:
    assert_exact_fields(item, *expected_fields)


class TestListResponsesAreAbbreviated:
    """Test that list endpoints return summary models with only summary fields."""

    def test_list_accounts_returns_summary_not_full_model(self, account_api: AccountApi) -> None:
        account_api.put("test-summary", AccountCreate(name="Test Summary"))
        account = find_item(account_api.list()["items"], "test-summary")
        _assert_summary_item(account, "id", "name")

    def test_list_players_returns_summary_not_full_model(self, player_api: PlayerApi) -> None:
        account_id = "test-summary-account"
        player_api.put(
            account_id,
            "test-summary-player",
            PlayerCreate.model_validate(
                {
                    "name": "Test Summary Player",
                    "stations_url": "https://example.com/custom-stations",
                    "switchboard_url": "wss://example.com/custom-switchboard",
                }
            ),
        )
        player = find_item(player_api.list(account_id)["items"], "test-summary-player")
        _assert_summary_item(player, "id", "account_id", "name")

    def test_list_global_presets_returns_summary_not_full_model(self, preset_api: PresetApi) -> None:
        preset_api.put_global(
            "test-summary-preset",
            GlobalStationPresetCreate.model_validate(
                {
                    "name": "Test Summary Preset",
                    "category": "Test Category",
                    "description": "This is a long description that should not appear in list responses",
                    "stations": [
                        {"name": "Station 1", "url": "https://station1.com"},
                        {"name": "Station 2", "url": "https://station2.com"},
                    ],
                }
            ),
        )

        items = preset_api.list_global()["items"]
        _assert_summary_item(find_item(items, "test-summary-preset"), "id", "name", "category")

        seeded_preset = find_item(items, "briceburg")
        assert "id" in seeded_preset
        assert "name" in seeded_preset
        assert "description" not in seeded_preset
        assert "stations" not in seeded_preset

    def test_list_account_presets_returns_summary_not_full_model(self, preset_api: PresetApi) -> None:
        account_id = "test-summary-account"
        preset_api.put_account(
            account_id,
            "test-summary-account-preset",
            AccountStationPresetCreate.model_validate(
                {
                    "name": "Test Summary Account Preset",
                    "category": "Test Category",
                    "description": "This description should not appear in list responses",
                    "stations": [
                        {"name": "Account Station 1", "url": "https://account-station1.com"},
                        {"name": "Account Station 2", "url": "https://account-station2.com"},
                    ],
                }
            ),
        )
        preset = find_item(preset_api.list_account(account_id)["items"], "test-summary-account-preset")
        _assert_summary_item(preset, "id", "account_id", "name", "category")

    def test_individual_get_endpoints_still_return_full_models(
        self, account_api: AccountApi, player_api: PlayerApi, preset_api: PresetApi
    ) -> None:
        account_id = "test-full-model"
        account_api.put(account_id, AccountCreate(name="Full Model Test"))

        player_api.put(
            account_id,
            "full-player",
            PlayerCreate.model_validate(
                {
                    "name": "Full Model Player",
                    "stations_url": "https://example.com/full-stations",
                    "switchboard_url": "wss://example.com/full-switchboard",
                }
            ),
        )
        preset_api.put_global(
            "full-preset",
            GlobalStationPresetCreate.model_validate(
                {
                    "name": "Full Model Preset",
                    "category": "Full Category",
                    "description": "Full description",
                    "stations": [{"name": "Full Station", "url": "https://full-station.com"}],
                }
            ),
        )
        preset_api.put_account(
            account_id,
            "full-account-preset",
            AccountStationPresetCreate.model_validate(
                {
                    "name": "Full Account Preset",
                    "category": "Full Category",
                    "description": "Full account description",
                    "stations": [{"name": "Full Account Station", "url": "https://full-account-station.com"}],
                }
            ),
        )

        account = account_api.get(account_id)
        assert "id" in account and "name" in account

        player = player_api.get(account_id, "full-player")
        assert "id" in player and "name" in player and "account_id" in player
        assert "stations_url" in player
        assert "switchboard_url" in player

        global_preset = preset_api.get_global("full-preset")
        assert "id" in global_preset and "name" in global_preset and "category" in global_preset
        assert "description" in global_preset
        assert "stations" in global_preset

        account_preset = preset_api.get_account(account_id, "full-account-preset")
        assert "id" in account_preset and "name" in account_preset and "account_id" in account_preset
        assert "description" in account_preset
        assert "stations" in account_preset
