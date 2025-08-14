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


def put_json(client, path: str, body: dict, expected: int = 200) -> dict:
    resp = client.put(path, json=body)
    assert resp.status_code == expected, f"expected {expected} got {resp.status_code}: {resp.text}"
    if expected == 200:
        return resp.json()
    return {}


def get_json(client, path: str, expected: int = 200) -> dict:
    resp = client.get(path)
    assert resp.status_code == expected, f"GET {path} expected {expected} got {resp.status_code}: {resp.text}"
    if expected == 200:
        return resp.json()
    return {}


def get_response(client, path: str, expected: int = 200):
    resp = client.get(path)
    assert resp.status_code == expected, f"GET {path} expected {expected} got {resp.status_code}: {resp.text}"
    return resp


def assert_paginated(payload: dict, total: int | None = None):
    for key in ("items", "total", "page", "per_page"):
        assert key in payload, f"Missing pagination key {key}"
    if total is not None:
        assert payload["total"] == total


def assert_item_fields(item: dict, **expected):
    for k, v in expected.items():
        assert item.get(k) == v, f"Field {k} expected {v} got {item.get(k)}"
