import pytest
from fastapi import status
from fastapi.routing import APIRoute

from api.models.pagination import PaginatedList
from tests.api._helpers import get_json

EXPECTED_PAGINATED_ENDPOINTS = {
    "/v1/accounts",
    "/v1/accounts/{account_id}/players",
    "/v1/presets",
    "/v1/accounts/{account_id}/presets",
}


def _normalize_path(path: str) -> str:
    if path != "/" and path.endswith("/"):
        return path[:-1]
    return path


def _discover_paginated_paths(app) -> set[str]:
    discovered: set[str] = set()
    for r in app.routes:
        if isinstance(r, APIRoute) and "GET" in (r.methods or set()):
            rm = getattr(r, "response_model", None)
            name = getattr(rm, "__name__", str(rm)) if rm else ""
            if rm and (
                "PaginatedList" in name
                or (
                    getattr(rm, "model_fields", None) and {"items", "page", "per_page"}.issubset(rm.model_fields.keys())
                )
            ):
                discovered.add(_normalize_path(r.path))
    return discovered


@pytest.mark.parametrize(
    "url",
    [
        "/v1/accounts",
        "/v1/accounts/testuser1/players",
        "/v1/presets",
    ],
)
def test_pagination_out_of_bounds(ro_client, url: str):
    data = get_json(ro_client, f"{url}?page=1000&per_page=1")
    assert len(data["items"]) == 0
    assert data["page"] == 1000
    assert data["per_page"] == 1
    # links sanity
    links = data["links"]
    assert links["prev"] == "?page=999&per_page=1"
    assert links.get("next") is None


@pytest.mark.parametrize(
    "url,item_count",
    [
        ("/v1/accounts", 2),
        ("/v1/accounts/testuser1/players", 2),
        ("/v1/presets", 1),
    ],
)
def test_per_page_and_link_behavior_single_page(ro_client, url: str, item_count: int):
    # per_page >= item_count
    data = get_json(ro_client, f"{url}?page=1&per_page={item_count + 5}")
    assert len(data["items"]) == item_count
    assert data["page"] == 1
    assert data["per_page"] == item_count + 5
    links = data["links"]
    assert links.get("prev") is None
    assert links.get("next") is None


@pytest.mark.parametrize(
    "url,item_id_1,item_id_2",
    [
        ("/v1/accounts", "testuser1", "testuser2"),
        ("/v1/accounts/testuser1/players", "player1", "player2"),
    ],
)
def test_pagination_works(ro_client, url: str, item_id_1: str, item_id_2: str):
    data = get_json(ro_client, f"{url}?page=1&per_page=1")
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == item_id_1
    assert data["page"] == 1
    assert data["per_page"] == 1
    links = data["links"]
    assert links.get("prev") is None
    assert links.get("next") == "?page=2&per_page=1"

    data = get_json(ro_client, f"{url}?page=2&per_page=1")
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == item_id_2
    assert data["page"] == 2
    assert data["per_page"] == 1
    links = data["links"]
    assert links.get("prev") == "?page=1&per_page=1"
    assert links.get("next") is not None

    # Follow the next link to the end
    data = get_json(ro_client, f"{url}{links['next']}")
    assert len(data["items"]) == 0
    assert data["page"] == 3
    assert data["links"]["next"] is None


# Unit-style tests for PaginatedList metadata (model-level)


def test_paginated_list_middle_page():
    pl = PaginatedList(items=[1] * 10, page=2, per_page=10)
    assert pl.has_prev is True
    assert pl.has_next is True
    assert pl.prev_page == 1
    assert pl.next_page == 3


def test_paginated_list_first_page():
    pl = PaginatedList(items=[1] * 10, page=1, per_page=10)
    assert pl.has_prev is False
    assert pl.prev_page is None
    assert pl.has_next is True
    assert pl.next_page == 2


def test_paginated_list_last_partial_page():
    pl = PaginatedList(items=[1, 2, 3], page=3, per_page=10)
    assert pl.has_next is False
    assert pl.next_page is None
    assert pl.has_prev is True
    assert pl.prev_page == 2


def test_paginated_list_single_page():
    pl = PaginatedList(items=[1, 2, 3], page=1, per_page=10)
    assert pl.has_next is False
    assert pl.has_prev is False
    assert pl.next_page is None
    assert pl.prev_page is None


@pytest.mark.parametrize(
    "raw_page,raw_per",
    [
        (0, 10),  # page too low
        (-1, 5),  # negative page
        (1, 0),  # per_page too low
        (1, 101),  # per_page too high (beyond max)
    ],
)
def test_pagination_invalid_values_rejected(ro_client, raw_page, raw_per):
    resp = ro_client.get(f"/v1/accounts?page={raw_page}&per_page={raw_per}")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = resp.json()["detail"]
    assert detail


def test_detect_new_paginated_endpoints(client):
    discovered = _discover_paginated_paths(client.app)
    extras = discovered - EXPECTED_PAGINATED_ENDPOINTS
    assert not extras, "New paginated endpoints detected; please add them to pagination tests: " + ", ".join(
        sorted(extras)
    )
