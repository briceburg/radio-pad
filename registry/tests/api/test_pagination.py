import pytest
from fastapi import status
from urllib.parse import urlparse, parse_qs
import math

from models.pagination import PaginatedList
from tests.api._helpers import get_json, put_json, get_response
from typing import get_origin
from fastapi.routing import APIRoute


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
            if rm and ("PaginatedList" in name or getattr(rm, "model_fields", None) and {"items","total","page","per_page"}.issubset(rm.model_fields.keys())):
                discovered.add(_normalize_path(r.path))
    return discovered


@pytest.mark.parametrize(
    "url,total",
    [
        ("/v1/accounts", 2),
        ("/v1/accounts/testuser1/players", 2),
        ("/v1/presets", 1),
    ],
)
def test_pagination_out_of_bounds(ro_client, url: str, total: int):
    data = get_json(ro_client, f"{url}?page=1000&per_page=1")
    assert len(data["items"]) == 0
    assert data["page"] == 1000
    assert data["per_page"] == 1
    assert data["total"] == total
    # links sanity
    links = data["links"]
    assert links["first"] == "?page=1&per_page=1"
    assert links["last"] == f"?page={total}&per_page=1"
    assert links["prev"] == f"?page={total}&per_page=1"
    assert links.get("next") is None


@pytest.mark.parametrize(
    "url,total",
    [
        ("/v1/accounts", 2),
        ("/v1/accounts/testuser1/players", 2),
        ("/v1/presets", 1),
    ],
)
def test_per_page_and_link_behavior_single_page(ro_client, url: str, total: int):
    # per_page == total
    data = get_json(ro_client, f"{url}?page=1&per_page={total}")
    assert len(data["items"]) == total
    assert data["page"] == 1
    assert data["per_page"] == total
    assert data["total"] == total
    links = data["links"]
    assert links["first"] == f"?page=1&per_page={total}"
    assert links["last"] == f"?page=1&per_page={total}"
    assert links.get("prev") is None
    assert links.get("next") is None

    # per_page > total (two variations)
    for extra in (1, 10):
        pp = total + extra
        data = get_json(ro_client, f"{url}?page=1&per_page={pp}")
        assert len(data["items"]) == total
        assert data["page"] == 1
        assert data["per_page"] == pp
        assert data["total"] == total
        links = data["links"]
        assert links["first"] == f"?page=1&per_page={pp}"
        assert links["last"] == f"?page=1&per_page={pp}"
        assert links.get("prev") is None
        assert links.get("next") is None


@pytest.mark.parametrize(
    "url,item_id_1,item_id_2,total",
    [
        ("/v1/accounts", "testuser1", "testuser2", 2),
        ("/v1/accounts/testuser1/players", "player1", "player2", 2),
    ],
)
def test_pagination_works(ro_client, url: str, item_id_1: str, item_id_2: str, total: int):
    data = get_json(ro_client, f"{url}?page=1&per_page=1")
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == item_id_1
    assert data["page"] == 1
    assert data["per_page"] == 1
    assert data["total"] == total
    links = data["links"]
    assert links["first"] == "?page=1&per_page=1"
    assert links["last"] == f"?page={total}&per_page=1"
    assert links.get("prev") is None
    assert links.get("next") == "?page=2&per_page=1"

    data = get_json(ro_client, f"{url}?page=2&per_page=1")
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == item_id_2
    assert data["page"] == 2
    assert data["per_page"] == 1
    assert data["total"] == total
    links = data["links"]
    assert links["first"] == "?page=1&per_page=1"
    assert links["last"] == f"?page={total}&per_page=1"
    assert links.get("prev") == "?page=1&per_page=1"
    assert links.get("next") is None


# Unit-style tests for PaginatedList metadata (model-level)


def test_paginated_list_middle_page():
    pl = PaginatedList(items=[1, 2, 3], total=25, page=2, per_page=10)
    assert pl.pages == 3
    assert pl.has_prev is True
    assert pl.has_next is True
    assert pl.prev_page == 1
    assert pl.next_page == 3


def test_paginated_list_first_page():
    pl = PaginatedList(items=[1, 2], total=23, page=1, per_page=10)
    assert pl.pages == 3
    assert pl.has_prev is False
    assert pl.prev_page is None
    assert pl.has_next is True
    assert pl.next_page == 2


def test_paginated_list_last_partial_page():
    pl = PaginatedList(items=[1, 2, 3], total=23, page=3, per_page=10)
    assert pl.pages == 3
    assert pl.has_next is False
    assert pl.next_page is None
    assert pl.has_prev is True
    assert pl.prev_page == 2


def test_paginated_list_exact_division_last_page():
    pl = PaginatedList(items=[1], total=30, page=3, per_page=10)
    assert pl.pages == 3
    assert pl.has_next is False
    assert pl.has_prev is True


def test_paginated_list_single_page():
    pl = PaginatedList(items=[1, 2, 3], total=3, page=1, per_page=10)
    assert pl.pages == 1
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


    


@pytest.mark.parametrize(
    "url,total",
    [
        ("/v1/accounts", 2),
        ("/v1/accounts/testuser1/players", 2),
        ("/v1/presets", 1),
    ],
)
def test_link_object_out_of_bounds_single_page(ro_client, url: str, total: int):
    # When per_page >= total, last_page=1 even if page is out of bounds
    big_pp = max(100, total)  # ensure single page
    data = get_json(ro_client, f"{url}?page=50&per_page={big_pp}")
    links = data["links"]
    assert links["first"] == f"?page=1&per_page={big_pp}"
    assert links["last"] == f"?page=1&per_page={big_pp}"
    assert links.get("prev") == f"?page=1&per_page={big_pp}"
    assert links.get("next") is None


def test_detect_new_paginated_endpoints(client):
    discovered = _discover_paginated_paths(client.app)
    extras = discovered - EXPECTED_PAGINATED_ENDPOINTS
    assert not extras, (
        "New paginated endpoints detected; please add them to pagination tests: "
        + ", ".join(sorted(extras))
    )
