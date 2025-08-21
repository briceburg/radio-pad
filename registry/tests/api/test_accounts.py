from http import HTTPStatus

import pytest
from fastapi import status
from starlette.testclient import TestClient

from api.models.pagination import PaginationParams
from models.account import AccountCreate
from tests.api._helpers import INVALID_SLUGS, assert_paginated
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


@pytest.mark.parametrize(
    "invalid_id",
    INVALID_SLUGS,
)
def test_account_invalid_id_rejected(client: TestClient, invalid_id: str) -> None:
    resp = client.put(f"/v1/accounts/{invalid_id}", json={"name": "Bad"})
    assert resp.status_code == 422


def test_account_partial_update_no_unintended_field_loss(client: TestClient) -> None:
    """Accounts only have name now; omitting future required fields should 422 (guard)."""
    resp = client.put("/v1/accounts/another-account", json={})
    assert resp.status_code == 422


def test_error_detail_shape_for_not_found(client: TestClient) -> None:
    # Non-existent account
    r = client.get("/v1/accounts/missing-account")
    assert r.status_code == HTTPStatus.NOT_FOUND
    body = r.json()
    assert set(body.keys()) == {"code", "message", "details"}
    assert body["code"] == "not_found"
    assert body["message"]
    assert body["details"]["account_id"] == "missing-account"


# --- Pagination Tests ---


def test_pagination_out_of_bounds(account_api: AccountApi) -> None:
    data = account_api.list(params=PaginationParams(page=1000, per_page=1))
    assert len(data["items"]) == 0
    assert data["page"] == 1000
    assert data["per_page"] == 1
    links = data["links"]
    assert links["prev"] == "?page=999&per_page=1"
    assert links.get("next") is None


def test_per_page_and_link_behavior_single_page(account_api: AccountApi) -> None:
    # per_page >= item_count
    data = account_api.list(params=PaginationParams(page=1, per_page=5))
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["per_page"] == 5
    links = data["links"]
    assert links.get("prev") is None
    assert links.get("next") is None


def test_pagination_works(account_api: AccountApi) -> None:
    data = account_api.list(params=PaginationParams(page=1, per_page=1))
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "testuser1"
    assert data["page"] == 1
    assert data["per_page"] == 1
    links = data["links"]
    assert links.get("prev") is None
    assert links.get("next") == "?page=2&per_page=1"

    data = account_api.list(params=PaginationParams(page=2, per_page=1))
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "testuser2"
    assert data["page"] == 2
    assert data["per_page"] == 1
    links = data["links"]
    assert links.get("prev") == "?page=1&per_page=1"
    assert links.get("next") is not None


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
    resp = client.get(f"/v1/accounts?page={raw_page}&per_page={raw_per}")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert resp.json()["detail"]
