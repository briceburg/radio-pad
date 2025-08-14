import json

import pytest
from starlette.testclient import TestClient

from registry import create_app


@pytest.mark.functional
def test_seeded_resources_are_loaded(functional_client):
    """Verify seed data for accounts, players, and global presets loads on startup."""
    # Accounts
    accounts_resp = functional_client.get("/v1/accounts")
    assert accounts_resp.status_code == 200
    accounts = accounts_resp.json()
    assert "briceburg" in [item["id"] for item in accounts["items"]]

    # Players under seeded account
    players_resp = functional_client.get("/v1/accounts/briceburg/players")
    assert players_resp.status_code == 200
    players = players_resp.json()
    assert "living-room" in [item["id"] for item in players["items"]]

    # Global presets
    presets_resp = functional_client.get("/v1/presets")
    assert presets_resp.status_code == 200
    presets = presets_resp.json()
    assert "briceburg" in [item["id"] for item in presets["items"]]


@pytest.mark.functional
def test_custom_seed_idempotency(tmp_path, monkeypatch):
    """Start app with custom seed dir, verify copy then idempotent on restart."""
    seed_dir = tmp_path / "seed"
    (seed_dir / "accounts").mkdir(parents=True)
    (seed_dir / "presets").mkdir(parents=True)
    (seed_dir / "accounts" / "acct-seeded.json").write_text(json.dumps({"name": "Seeded Account"}))
    (seed_dir / "presets" / "jazz.json").write_text(json.dumps({"name": "Jazz", "stations": []}))

    data_dir = tmp_path / "data"
    monkeypatch.setenv("REGISTRY_PATH_DATA", str(data_dir))
    monkeypatch.setenv("REGISTRY_PATH_SEED", str(seed_dir))

    app = create_app()
    with TestClient(app) as client:
        accounts = client.get("/v1/accounts").json()
        assert any(a["id"] == "acct-seeded" for a in accounts["items"])
        presets = client.get("/v1/presets").json()
        assert any(p["id"] == "jazz" for p in presets["items"])

    acct_file = data_dir / "accounts" / "acct-seeded.json"
    acct_file.write_text(json.dumps({"name": "Modified"}))

    app2 = create_app()
    with TestClient(app2) as client:
        accounts2 = client.get("/v1/accounts").json()
        assert any(a["id"] == "acct-seeded" for a in accounts2["items"])
        assert acct_file.read_text() == json.dumps({"name": "Modified"})
    assert (data_dir / "presets" / "jazz.json").is_file()
