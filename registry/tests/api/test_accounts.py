import pytest
from fastapi import status
from starlette.testclient import TestClient

from models.account import AccountCreate
from tests.api._helpers import assert_paginated
from tests.api.client.accounts import AccountApi


def test_list_accounts(account_api: AccountApi) -> None:
    data = account_api.list()
    assert_paginated(data)
    assert len(data["items"]) == 2
    for account in data["items"]:
        assert "id" in account and "name" in account


def test_register_account(account_api: AccountApi) -> None:
    """Test that a new account can be created."""
    account_api.put("new-account", AccountCreate(name="New Account"))
    data = account_api.list()
    assert len(data["items"]) == 3
    assert "new-account" in [item["id"] for item in data["items"]]


def test_update_account(account_api: AccountApi) -> None:
    """Test that an existing account can be updated."""
    account_api.put("testuser1", AccountCreate(name="Updated Name"))
    data = account_api.list()
    assert len(data["items"]) == 2
    assert any(item["id"] == "testuser1" and item["name"] == "Updated Name" for item in data["items"])


def test_account_partial_update_no_unintended_field_loss(client: TestClient) -> None:
    """Accounts only have name now; omitting future required fields should 422 (guard)."""
    resp = client.put("accounts/another-account", json={})
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "raw_page,raw_per",
    [
        (0, 10),  # page too low
        (-1, 5),  # negative page
        (1, 0),  # per_page too low
        (1, 101),  # per_page too high (beyond max)
    ],
)
def test_pagination_invalid_values_rejected(client: TestClient, raw_page: int, raw_per: int) -> None:
    resp = client.get(f"accounts?page={raw_page}&per_page={raw_per}")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert resp.json()["detail"]
