from typing import Protocol

from pydantic import BaseModel
from starlette.testclient import TestClient

from api.models.pagination import PaginatedList, PaginationParams
from datastore.types import JsonDoc


class _ResponseLike(Protocol):
    @property
    def status_code(self) -> int: ...

    @property
    def text(self) -> str: ...

    def json(self) -> JsonDoc: ...


# Common slug cases reused across tests
INVALID_SLUGS = [
    "Invalid",  # uppercase first letter
    "has space",  # whitespace
    "UPPER",  # all caps
    "mixedCase",  # camel/mixed
    "trailing-",  # trailing dash
    "-leading",  # leading dash
    "bad_id",  # underscore
    "bad--id",  # double dash
]

VALID_SLUG_EDGE_CASES = [
    "a",
    "abc",
    "abc-def",
    "abc-def-123",
]

# Pairs of (account_id, player/preset id) that are valid slugs
VALID_ACCOUNT_ITEM_SLUG_PAIRS = [
    ("a", "a"),
    ("abc", "abc-def"),
    ("abc-def-123", "player-123"),
]


def _request_path(path: str) -> str:
    return path[1:] if path.startswith("/") else path


def put_json(client: TestClient, path: str, body: JsonDoc | BaseModel, expected: int = 200) -> JsonDoc:
    payload = body if isinstance(body, dict) else body.model_dump(mode="json", exclude_none=True)
    resp = client.put(_request_path(path), json=payload)
    assert resp.status_code == expected, f"expected {expected} got {resp.status_code}: {resp.text}"
    if expected == 200:
        data: JsonDoc = resp.json()
        return data
    return {}


def get_json(client: TestClient, path: str, expected: int = 200, params: PaginationParams | None = None) -> JsonDoc:
    # Pydantic models must be converted to dicts for query params
    params_dict = params.model_dump(exclude_none=True) if params else None
    resp = client.get(_request_path(path), params=params_dict)
    assert resp.status_code == expected, f"GET {path} expected {expected} got {resp.status_code}: {resp.text}"
    if expected == 200:
        data: JsonDoc = resp.json()
        return data
    return {}


def get_response(client: TestClient, path: str, expected: int = 200) -> _ResponseLike:
    resp = client.get(_request_path(path))
    assert resp.status_code == expected, f"GET {path} expected {expected} got {resp.status_code}: {resp.text}"
    return resp


def assert_paginated(payload: JsonDoc) -> None:
    # Validate against our typed PaginatedList model to ensure shape is correct
    try:
        PaginatedList[JsonDoc].model_validate(payload)
    except Exception as e:
        raise AssertionError(f"Payload is not a valid PaginatedList: {e}; payload={payload}") from e

    # Keep a few explicit keys for clearer failure messages in callers
    for key in ("items", "page", "per_page"):
        assert key in payload, f"Missing pagination key {key}"


def assert_pagination_page(
    payload: JsonDoc,
    *,
    item_ids: list[str],
    page: int,
    per_page: int,
    prev: str | None,
    next: str | None,
) -> None:
    assert_paginated(payload)
    assert [str(item["id"]) for item in payload["items"]] == item_ids
    assert payload["page"] == page
    assert payload["per_page"] == per_page
    links = payload["links"]
    assert links.get("prev") == prev
    assert links.get("next") == next


def assert_item_fields(item: JsonDoc, **expected: object) -> None:
    for k, v in expected.items():
        assert item.get(k) == v, f"Field {k} expected {v} got {item.get(k)}"


def assert_exact_fields(item: JsonDoc, *expected_fields: str) -> None:
    expected = set(expected_fields)
    actual = set(str(key) for key in item.keys())
    assert actual == expected, f"Expected only {expected}, got {actual}"


def find_item(items: list[JsonDoc], object_id: str) -> JsonDoc:
    for item in items:
        if item.get("id") == object_id:
            return item
    raise AssertionError(f"Expected to find item with id={object_id!r}")
