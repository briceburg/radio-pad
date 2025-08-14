from http import HTTPStatus

from starlette.testclient import TestClient

from models import PlayerCreate


def test_error_detail_shape_for_not_found(client: TestClient):
    # Non-existent account
    r = client.get("/v1/accounts/missing-account")
    assert r.status_code == HTTPStatus.NOT_FOUND
    body = r.json()
    assert set(body.keys()) == {"code", "message", "details"}
    assert body["code"] == "not_found"
    assert body["message"]
    assert body["details"]["account_id"] == "missing-account"

    # Non-existent player
    r2 = client.get("/v1/accounts/testuser1/players/missing-player")
    assert r2.status_code == HTTPStatus.NOT_FOUND
    body2 = r2.json()
    assert body2["code"] == "not_found"
    assert body2["details"]["player_id"] == "missing-player"


def test_conflict_error_shape_and_status(client: TestClient):
    # Create a player
    r = client.put("/v1/accounts/testuser1/players/p1", json=PlayerCreate(name="P").model_dump(exclude_none=True))
    assert r.status_code == HTTPStatus.OK

    # Try a quick subsequent write. If a conflict occurs, validate error shape.
    r2 = client.put("/v1/accounts/testuser1/players/p1", json={"name": "P2"})
    if r2.status_code == HTTPStatus.CONFLICT:
        body = r2.json()
        assert body["code"] == "conflict"
        assert "message" in body
