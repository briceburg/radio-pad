"""Tests to ensure list endpoints return abbreviated summary models, not full models."""

from models.account import AccountCreate
from models.player import PlayerCreate
from models.station_preset import AccountStationPresetCreate, GlobalStationPresetCreate
from tests.api.client.accounts import AccountApi
from tests.api.client.players import PlayerApi
from tests.api.client.presets import PresetApi


class TestListResponsesAreAbbreviated:
    """Test that list endpoints return summary models with only id, name, and category fields."""

    def test_list_accounts_returns_summary_not_full_model(self, account_api: AccountApi) -> None:
        """List accounts should return only id and name, no other fields."""
        # Create an account to ensure we have data
        account_api.put("test-summary", AccountCreate(name="Test Summary"))

        data = account_api.list()
        assert len(data["items"]) > 0

        account = data["items"][0]
        # Should have summary fields
        assert "id" in account
        assert "name" in account

        # Should NOT have any other fields that might be in full model
        # (Account model is simple, but this ensures we're returning the right model)
        expected_fields = {"id", "name"}
        actual_fields = set(account.keys())
        assert actual_fields == expected_fields, f"Expected only {expected_fields}, got {actual_fields}"

    def test_list_players_returns_summary_not_full_model(self, player_api: PlayerApi) -> None:
        """List players should return only id, account_id, and name, not stations_url or switchboard_url."""
        account_id = "test-summary-account"

        # Create a player with full data
        player_data = PlayerCreate.model_validate(
            {
                "name": "Test Summary Player",
                "stations_url": "https://example.com/custom-stations",
                "switchboard_url": "wss://example.com/custom-switchboard",
            }
        )
        player_api.put(account_id, "test-summary-player", player_data)

        # List players
        data = player_api.list(account_id)
        assert len(data["items"]) > 0

        player = data["items"][0]
        # Should have summary fields
        assert "id" in player
        assert "account_id" in player
        assert "name" in player

        # Should NOT have full model fields
        assert "stations_url" not in player, "List should not include stations_url"
        assert "switchboard_url" not in player, "List should not include switchboard_url"

        # Verify exact fields
        expected_fields = {"id", "account_id", "name"}
        actual_fields = set(player.keys())
        assert actual_fields == expected_fields, f"Expected only {expected_fields}, got {actual_fields}"

    def test_list_global_presets_returns_summary_not_full_model(self, preset_api: PresetApi) -> None:
        """List global presets should return only id, name, and category, not description or stations."""
        # Create a preset with full data including stations and description
        preset_data = GlobalStationPresetCreate.model_validate(
            {
                "name": "Test Summary Preset",
                "category": "Test Category",
                "description": "This is a long description that should not appear in list responses",
                "stations": [
                    {"name": "Station 1", "url": "https://station1.com"},
                    {"name": "Station 2", "url": "https://station2.com"},
                ],
            }
        )
        preset_api.put_global("test-summary-preset", preset_data)

        # List presets
        data = preset_api.list_global()
        assert len(data["items"]) > 0

        # Find our test preset (there may be seeded data without categories)
        test_preset = None
        for preset in data["items"]:
            if preset.get("id") == "test-summary-preset":
                test_preset = preset
                break

        assert test_preset is not None, "Should find our test preset in the list"

        # Should have summary fields
        assert "id" in test_preset
        assert "name" in test_preset
        assert "category" in test_preset

        # Should NOT have full model fields
        assert "description" not in test_preset, "List should not include description"
        assert "stations" not in test_preset, "List should not include stations array"

        # Verify exact fields for our test data (category should be present since we set it)
        expected_fields = {"id", "name", "category"}
        actual_fields = set(test_preset.keys())
        assert actual_fields == expected_fields, f"Expected only {expected_fields}, got {actual_fields}"

        # Also test that seeded data without category still works (category excluded when None)
        seeded_preset = None
        for preset in data["items"]:
            if preset.get("id") == "briceburg":  # This is from seed data
                seeded_preset = preset
                break

        if seeded_preset is not None:
            # Seeded preset should have id and name, but category may be excluded if None
            assert "id" in seeded_preset
            assert "name" in seeded_preset
            # Category may or may not be present (excluded when None due to response_model_exclude_none)
            assert "description" not in seeded_preset, "List should not include description"
            assert "stations" not in seeded_preset, "List should not include stations array"

    def test_list_account_presets_returns_summary_not_full_model(self, preset_api: PresetApi) -> None:
        """List account presets should return only id, account_id, name, and category."""
        account_id = "test-summary-account"

        # Create a preset with full data
        preset_data = AccountStationPresetCreate.model_validate(
            {
                "name": "Test Summary Account Preset",
                "category": "Test Category",
                "description": "This description should not appear in list responses",
                "stations": [
                    {"name": "Account Station 1", "url": "https://account-station1.com"},
                    {"name": "Account Station 2", "url": "https://account-station2.com"},
                ],
            }
        )
        preset_api.put_account(account_id, "test-summary-account-preset", preset_data)

        # List presets
        data = preset_api.list_account(account_id)
        assert len(data["items"]) > 0

        preset = data["items"][0]
        # Should have summary fields
        assert "id" in preset
        assert "account_id" in preset
        assert "name" in preset
        assert "category" in preset

        # Should NOT have full model fields
        assert "description" not in preset, "List should not include description"
        assert "stations" not in preset, "List should not include stations array"

        # Verify exact fields
        expected_fields = {"id", "account_id", "name", "category"}
        actual_fields = set(preset.keys())
        assert actual_fields == expected_fields, f"Expected only {expected_fields}, got {actual_fields}"

    def test_individual_get_endpoints_still_return_full_models(
        self, account_api: AccountApi, player_api: PlayerApi, preset_api: PresetApi
    ) -> None:
        """Verify that individual GET endpoints still return full models with all fields."""
        account_id = "test-full-model"

        # Create resources
        account_api.put(account_id, AccountCreate(name="Full Model Test"))

        player_data = PlayerCreate.model_validate(
            {
                "name": "Full Model Player",
                "stations_url": "https://example.com/full-stations",
                "switchboard_url": "wss://example.com/full-switchboard",
            }
        )
        player_api.put(account_id, "full-player", player_data)

        preset_data = GlobalStationPresetCreate.model_validate(
            {
                "name": "Full Model Preset",
                "category": "Full Category",
                "description": "Full description",
                "stations": [{"name": "Full Station", "url": "https://full-station.com"}],
            }
        )
        preset_api.put_global("full-preset", preset_data)

        account_preset_data = AccountStationPresetCreate.model_validate(
            {
                "name": "Full Account Preset",
                "category": "Full Category",
                "description": "Full account description",
                "stations": [{"name": "Full Account Station", "url": "https://full-account-station.com"}],
            }
        )
        preset_api.put_account(account_id, "full-account-preset", account_preset_data)

        # Get individual resources - should have full models
        account = account_api.get(account_id)
        assert "id" in account and "name" in account

        player = player_api.get(account_id, "full-player")
        assert "id" in player and "name" in player and "account_id" in player
        assert "stations_url" in player, "Individual GET should include stations_url"
        assert "switchboard_url" in player, "Individual GET should include switchboard_url"

        global_preset = preset_api.get_global("full-preset")
        assert "id" in global_preset and "name" in global_preset and "category" in global_preset
        assert "description" in global_preset, "Individual GET should include description"
        assert "stations" in global_preset, "Individual GET should include stations"

        account_preset = preset_api.get_account(account_id, "full-account-preset")
        assert "id" in account_preset and "name" in account_preset and "account_id" in account_preset
        assert "description" in account_preset, "Individual GET should include description"
        assert "stations" in account_preset, "Individual GET should include stations"
