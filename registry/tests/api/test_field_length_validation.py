"""Tests to validate field length constraints are properly enforced."""

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from lib.constants import MAX_DESCRIPTOR_LENGTH
from models.account import AccountCreate
from models.player import PlayerCreate
from models.station_preset import AccountStationPresetCreate, GlobalStationPresetCreate


class TestFieldLengthValidation:
    """Test that name, category, and ID fields are properly constrained to MAX_DESCRIPTOR_LENGTH characters."""

    def test_account_name_length_constraint(self) -> None:
        """Account names should be limited to MAX_DESCRIPTOR_LENGTH characters."""
        # Valid name (MAX_DESCRIPTOR_LENGTH characters exactly)
        valid_name = "a" * MAX_DESCRIPTOR_LENGTH
        account = AccountCreate(name=valid_name)
        assert account.name == valid_name

        # Invalid name (MAX_DESCRIPTOR_LENGTH + 1 characters)
        invalid_name = "a" * (MAX_DESCRIPTOR_LENGTH + 1)
        with pytest.raises(ValidationError) as exc_info:
            AccountCreate(name=invalid_name)
        assert f"String should have at most {MAX_DESCRIPTOR_LENGTH} characters" in str(exc_info.value)

    def test_player_name_length_constraint(self) -> None:
        """Test PlayerCreate name field length validation."""
        valid_name = "a" * MAX_DESCRIPTOR_LENGTH
        invalid_name = "a" * (MAX_DESCRIPTOR_LENGTH + 1)

        # Valid name should work
        player = PlayerCreate.model_validate({"name": valid_name})
        assert player.name == valid_name

        # Invalid name should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            PlayerCreate.model_validate({"name": invalid_name})
        assert "String should have at most" in str(exc_info.value)

    def test_station_preset_name_length_constraint(self) -> None:
        """Test that station preset name field length validation works."""
        valid_name = "a" * MAX_DESCRIPTOR_LENGTH
        invalid_name = "a" * (MAX_DESCRIPTOR_LENGTH + 1)
        stations = [{"name": "Test Station", "url": "https://example.com/stream"}]

        # Valid names should work
        global_preset = GlobalStationPresetCreate.model_validate({"name": valid_name, "stations": stations})
        assert global_preset.name == valid_name

        account_preset = AccountStationPresetCreate.model_validate({"name": valid_name, "stations": stations})
        assert account_preset.name == valid_name

        # Invalid names should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            GlobalStationPresetCreate.model_validate({"name": invalid_name, "stations": stations})
        assert "String should have at most" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            AccountStationPresetCreate.model_validate({"name": invalid_name, "stations": stations})
        assert "String should have at most" in str(exc_info.value)

    def test_preset_category_length_constraint(self) -> None:
        """Preset categories should be limited to MAX_DESCRIPTOR_LENGTH characters."""
        stations = [{"name": "Test", "url": "https://test.com"}]

        # Valid category (MAX_DESCRIPTOR_LENGTH characters exactly)
        valid_category = "b" * MAX_DESCRIPTOR_LENGTH
        global_preset = GlobalStationPresetCreate.model_validate(
            {"name": "Test", "category": valid_category, "stations": stations}
        )
        assert global_preset.category == valid_category

        account_preset = AccountStationPresetCreate.model_validate(
            {"name": "Test", "category": valid_category, "stations": stations}
        )
        assert account_preset.category == valid_category

        # Invalid category (MAX_DESCRIPTOR_LENGTH + 1 characters)
        invalid_category = "b" * (MAX_DESCRIPTOR_LENGTH + 1)
        with pytest.raises(ValidationError) as exc_info:
            GlobalStationPresetCreate.model_validate(
                {"name": "Test", "category": invalid_category, "stations": stations}
            )
        assert f"String should have at most {MAX_DESCRIPTOR_LENGTH} characters" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            AccountStationPresetCreate.model_validate(
                {"name": "Test", "category": invalid_category, "stations": stations}
            )
        assert f"String should have at most {MAX_DESCRIPTOR_LENGTH} characters" in str(exc_info.value)

    def test_slug_id_length_constraint_via_api(self, client: TestClient) -> None:
        """IDs (slugs) should be limited to MAX_DESCRIPTOR_LENGTH characters via the Slug type constraint."""

        # Valid ID (MAX_DESCRIPTOR_LENGTH characters exactly - all lowercase with hyphens)
        valid_id = "a" * (MAX_DESCRIPTOR_LENGTH - 1) + "1"  # MAX_DESCRIPTOR_LENGTH chars, valid slug format
        resp = client.put(f"/v1/accounts/{valid_id}", json={"name": "Test"})
        assert resp.status_code == 200

        # Invalid ID (MAX_DESCRIPTOR_LENGTH + 1 characters)
        invalid_id = "a" * MAX_DESCRIPTOR_LENGTH + "1"  # MAX_DESCRIPTOR_LENGTH + 1 chars
        resp = client.put(f"/v1/accounts/{invalid_id}", json={"name": "Test"})
        assert resp.status_code == 422  # Validation error
        error_detail = resp.json()
        # Should have validation error about slug length
        assert "detail" in error_detail

    def test_length_constraint_allows_guid_length(self) -> None:
        """Verify that MAX_DESCRIPTOR_LENGTH characters is sufficient for GUIDs as requested."""
        # Standard GUID format is 36 characters with hyphens: 8-4-4-4-12
        # Example: "123e4567-e89b-12d3-a456-426614174000"
        guid_like_name = "123e4567-e89b-12d3-a456-426614174000"
        assert len(guid_like_name) == MAX_DESCRIPTOR_LENGTH

        # Should work for all name fields
        account = AccountCreate(name=guid_like_name)
        assert account.name == guid_like_name

        player = PlayerCreate.model_validate({"name": guid_like_name})
        assert player.name == guid_like_name

        stations = [{"name": "Test", "url": "https://test.com"}]
        global_preset = GlobalStationPresetCreate.model_validate(
            {"name": guid_like_name, "category": guid_like_name, "stations": stations}
        )
        assert global_preset.name == guid_like_name
        assert global_preset.category == guid_like_name
