import pytest

from tests.api._helpers import assert_paginated, get_json, put_json


def test_list_accounts(ro_client):
    data = get_json(ro_client, "/v1/accounts")
    assert_paginated(data)
    assert len(data["items"]) == 2
    for account in data["items"]:
        assert "id" in account and "name" in account


def test_register_account(client):
    """Test that a new account can be created."""
    put_json(client, "/v1/accounts/new-account", {"name": "New Account"})
    data = get_json(client, "/v1/accounts")
    assert len(data["items"]) == 3
    assert "new-account" in [item["id"] for item in data["items"]]


def test_update_account(client):
    """Test that an existing account can be updated."""
    put_json(client, "/v1/accounts/testuser1", {"name": "Updated Name"})
    data = get_json(client, "/v1/accounts")
    assert len(data["items"]) == 2
    assert any(item["id"] == "testuser1" and item["name"] == "Updated Name" for item in data["items"])


@pytest.mark.parametrize(
    "invalid_id",
    ["Invalid", "has space", "UPPER", "mixedCase", "trailing-", "-leading"],
)
def test_account_invalid_id_rejected(client, invalid_id):
    resp = client.put(f"/v1/accounts/{invalid_id}", json={"name": "Bad"})
    assert resp.status_code == 422


def test_account_partial_update_no_unintended_field_loss(client):
    """Accounts only have name now; omitting future required fields should 422 (guard)."""
    resp = client.put("/v1/accounts/another-account", json={})
    assert resp.status_code == 422
