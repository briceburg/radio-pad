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


def put_json(client: TestClient, path: str, body: JsonDoc | BaseModel, expected: int = 200) -> JsonDoc:
    payload = body if isinstance(body, dict) else body.model_dump(mode="json", exclude_none=True)
    resp = client.put(path, json=payload)
    assert resp.status_code == expected, f"expected {expected} got {resp.status_code}: {resp.text}"
    if expected == 200:
        data: JsonDoc = resp.json()
        return data
    return {}


def get_json(client: TestClient, path: str, expected: int = 200, params: PaginationParams | None = None) -> JsonDoc:
    # Pydantic models must be converted to dicts for query params
    params_dict = params.model_dump(exclude_none=True) if params else None
    resp = client.get(path, params=params_dict)
    assert resp.status_code == expected, f"GET {path} expected {expected} got {resp.status_code}: {resp.text}"
    if expected == 200:
        data: JsonDoc = resp.json()
        return data
    return {}


def get_response(client: TestClient, path: str, expected: int = 200) -> _ResponseLike:
    resp = client.get(path)
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


def assert_item_fields(item: JsonDoc, **expected: object) -> None:
    for k, v in expected.items():
        assert item.get(k) == v, f"Field {k} expected {v} got {item.get(k)}"
