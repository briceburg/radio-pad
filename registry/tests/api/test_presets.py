from http import HTTPStatus

import pytest

from tests.api._helpers import (
    INVALID_SLUGS,
    VALID_ACCOUNT_ITEM_SLUG_PAIRS,
    VALID_SLUG_EDGE_CASES,
    assert_item_fields,
    assert_paginated,
    get_json,
    put_json,
)

# -------------------- Global Presets --------------------


def test_list_global_presets(ro_client):
    data = get_json(ro_client, "/v1/presets")
    assert_paginated(data)


def test_get_global_preset(client):
    preset_id = "test-preset"
    put_json(
        client,
        f"/v1/presets/{preset_id}",
        {"name": "Test Preset", "stations": [{"name": "A", "url": "https://a.com"}]},
    )
    data = get_json(client, f"/v1/presets/{preset_id}")
    assert data["id"] == preset_id
    assert isinstance(data["stations"], list)


def test_get_global_preset_not_found(ro_client):
    get_json(ro_client, "/v1/presets/does-not-exist", expected=404)


def test_register_global_preset_full_payload(client):
    preset_id = "new-global-preset"
    payload = {
        "name": "New Global Preset",
        "category": "News",
        "description": "A collection of news stations.",
        "stations": [
            {"name": "A Cool Station", "url": "https://cool.station/stream"},
        ],
    }
    data = put_json(client, f"/v1/presets/{preset_id}", payload)
    assert_item_fields(
        data,
        id=preset_id,
        name=payload["name"],
        category=payload["category"],
        description=payload["description"],
    )
    assert "account_id" not in data


@pytest.mark.parametrize("invalid_id", INVALID_SLUGS)
def test_global_preset_invalid_id_rejected(client, invalid_id):
    resp = client.put(f"/v1/presets/{invalid_id}", json={"name": "X", "stations": []})
    assert resp.status_code == 422


# -------------------- Account Presets --------------------


@pytest.mark.parametrize(
    "preset_id,payload",
    [
        ("my-preset", {"name": "My Preset", "stations": [{"name": "A", "url": "https://a.com"}]}),
        (
            "my-custom-preset",
            {
                "name": "My Custom Preset",
                "category": "Personal",
                "description": "My personal list of stations.",
                "stations": [
                    {"name": "A Cool Station", "url": "https://cool.station/stream"},
                ],
            },
        ),
    ],
)
def test_account_preset_create_and_get(client, preset_id, payload):
    account_id = "testuser"
    put_data = put_json(
        client,
        f"/v1/accounts/{account_id}/presets/{preset_id}",
        payload,
    )
    assert_item_fields(
        put_data,
        id=preset_id,
        account_id=account_id,
        name=payload["name"],
    )

    get_data = get_json(client, f"/v1/accounts/{account_id}/presets/{preset_id}")
    assert_item_fields(get_data, id=preset_id, account_id=account_id)


def test_get_account_preset_not_found(ro_client):
    get_json(ro_client, "/v1/accounts/testuser/presets/does-not-exist", expected=404)


def test_list_account_presets(client):
    account_id = "testuser"
    put_json(
        client,
        f"/v1/accounts/{account_id}/presets/list-one",
        {"name": "List One", "stations": [{"name": "A", "url": "https://a.com"}]},
    )
    data = get_json(client, f"/v1/accounts/{account_id}/presets")
    assert_paginated(data)
    assert len(data["items"]) == 1
    assert_item_fields(data["items"][0], id="list-one", account_id=account_id)


@pytest.mark.parametrize(
    "invalid_id",
    [
        "Invalid",
        "has space",
        "UPPER",
        "mixedCase",
        "trailing-",
        "-leading",
        "bad_id",
        "bad--id",
    ],
)
def test_account_preset_invalid_id_rejected(client, invalid_id):
    resp = client.put(
        f"/v1/accounts/testuser/presets/{invalid_id}",
        json={"name": "X", "stations": []},
    )
    assert resp.status_code == 422


# New: invalid account_id path segment should 422
@pytest.mark.parametrize("invalid_account_id", INVALID_SLUGS)
def test_preset_invalid_account_id_rejected(client, invalid_account_id):
    resp = client.put(
        f"/v1/accounts/{invalid_account_id}/presets/pid",
        json={"name": "X", "stations": []},
    )
    assert resp.status_code == 422


# -------------------- Validation (Success & Failure) --------------------
# Success cases cover both global and account scoped minimal payloads.
@pytest.mark.parametrize(
    "url_template,preset_id",
    [
        ("/v1/presets/{preset_id}", "valid-global-min"),
        ("/v1/accounts/testuser/presets/{preset_id}", "valid-account-min"),
    ],
)
def test_preset_create_minimal_success(client, url_template, preset_id):
    data = put_json(
        client,
        url_template.format(preset_id=preset_id),
        {"name": "Valid", "stations": []},
    )
    assert_item_fields(data, id=preset_id, name="Valid")
    assert isinstance(data["stations"], list)


# Failure cases parametrize missing required fields across scopes.
@pytest.mark.parametrize(
    "url_template,body",
    [
        ("/v1/presets/{preset_id}", {"stations": []}),  # missing name
        ("/v1/presets/{preset_id}", {"name": "No Stations"}),  # missing stations
        ("/v1/accounts/testuser/presets/{preset_id}", {"stations": []}),
        ("/v1/accounts/testuser/presets/{preset_id}", {"name": "No Stations"}),
    ],
)
def test_preset_create_validation_failures(client, url_template, body):
    preset_id = "invalid"
    resp = client.put(url_template.format(preset_id=preset_id), json=body)
    assert resp.status_code == 422
    assert resp.json()["detail"]


"""Positive edge-case slug acceptance across both global and account scopes."""

# Build a combined parameter set for both scopes to reduce duplication
EDGE_CASE_PARAMS = [("/v1/presets/{preset_id}", {}, preset_id) for preset_id in VALID_SLUG_EDGE_CASES] + [
    (
        "/v1/accounts/{account_id}/presets/{preset_id}",
        {"account_id": account_id},
        preset_id,
    )
    for account_id, preset_id in VALID_ACCOUNT_ITEM_SLUG_PAIRS
]


@pytest.mark.parametrize("url_tpl,ctx,preset_id", EDGE_CASE_PARAMS)
def test_preset_valid_slug_edge_cases(client, url_tpl, ctx, preset_id):
    url = url_tpl.format(preset_id=preset_id, **ctx)
    resp = client.put(url, json={"name": "Edge", "stations": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == preset_id
    if ctx:
        assert data["account_id"] == ctx["account_id"]


@pytest.mark.parametrize(
    "url_tpl,ctx",
    [
        ("/v1/presets/{id}", {}),
        ("/v1/accounts/{account_id}/presets/{id}", {"account_id": "testuser"}),
    ],
)
def test_preset_partial_update_persists_other_fields(client, url_tpl, ctx):
    """Create preset with optional fields then update only name; other fields persist for both scopes."""
    preset_id = "partial"
    url = url_tpl.format(id=preset_id, **ctx)
    initial = {
        "name": "Original",
        "category": "Music",
        "description": "Desc",
        "stations": [{"name": "A", "url": "https://a.com"}],
    }
    created = put_json(client, url, initial)
    assert_item_fields(
        created,
        id=preset_id,
        name="Original",
        category="Music",
        description="Desc",
        **({"account_id": ctx["account_id"]} if ctx else {}),
    )
    # Update only name (account requires stations in payload)
    update_body = {"name": "Renamed"}
    if ctx:
        update_body["stations"] = initial["stations"]
    else:
        update_body["stations"] = []
    updated = put_json(client, url, update_body)
    assert_item_fields(
        updated,
        id=preset_id,
        name="Renamed",
        category="Music",
        description="Desc",
        **({"account_id": ctx["account_id"]} if ctx else {}),
    )


def test_preset_rejects_duplicate_station_names(client):
    payload = {
        "name": "Dup Names",
        "stations": [
            {"name": "Same", "url": "https://a.example/stream"},
            {"name": "same", "url": "https://b.example/stream"},
        ],
    }
    resp = client.put("/v1/presets/dup-names", json=payload)
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    body = resp.json()
    assert any("Duplicate station name" in (err.get("msg") or str(err)) for err in body.get("detail", []))


def test_preset_rejects_duplicate_station_urls(client):
    payload = {
        "name": "Dup URLs",
        "stations": [
            {"name": "A", "url": "https://same.example/stream"},
            {"name": "B", "url": "https://same.example/stream"},
        ],
    }
    resp = client.put("/v1/presets/dup-urls", json=payload)
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    body = resp.json()
    assert any("Duplicate station URL" in (err.get("msg") or str(err)) for err in body.get("detail", []))
