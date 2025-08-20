import json

import boto3
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

    # Players
    players_resp = functional_client.get("/v1/accounts/briceburg/players")
    assert players_resp.status_code == 200
    players = players_resp.json()
    assert "living-room" in [item["id"] for item in players["items"]]

    # Global Presets
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
    monkeypatch.setenv("REGISTRY_BACKEND_PATH", str(data_dir))
    monkeypatch.setenv("REGISTRY_SEED_PATH", str(seed_dir))

    app = create_app()
    with TestClient(app) as client:
        accounts = client.get("/v1/accounts").json()
        assert any(a["id"] == "acct-seeded" for a in accounts["items"])

        # Tamper with the data to ensure it is not overwritten on next startup
        (data_dir / "registry-v1" / "accounts" / "acct-seeded.json").write_text(
            json.dumps({"name": "TAMPERED"})
        )

    # Re-create the app and client to trigger lifespan startup again
    app2 = create_app()
    with TestClient(app2) as client2:
        resp = client2.get("/v1/accounts/acct-seeded")
        assert resp.json()["name"] == "TAMPERED"


@pytest.mark.functional
@pytest.mark.s3
def test_s3_seeding(s3_test_bucket, tmp_path, monkeypatch):
    """Verify seeding works with the S3 backend."""
    seed_dir = tmp_path / "seed"
    (seed_dir / "accounts").mkdir(parents=True)
    (seed_dir / "accounts" / "s3-acct.json").write_text(json.dumps({"name": "S3 Account"}))

    monkeypatch.setenv("REGISTRY_BACKEND", "s3")
    monkeypatch.setenv("REGISTRY_BACKEND_S3_BUCKET", s3_test_bucket)
    monkeypatch.setenv("REGISTRY_SEED_PATH", str(seed_dir))

    # Create the app to trigger the seeding via the lifespan event
    app = create_app()
    with TestClient(app):
        # Verify the object was created in S3
        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket=s3_test_bucket, Key="registry-v1/accounts/s3-acct.json")
        data = json.loads(obj["Body"].read())
        assert data["name"] == "S3 Account"


@pytest.mark.functional
@pytest.mark.s3
def test_s3_seed_idempotency(s3_test_bucket, tmp_path, monkeypatch):
    """Verify S3 seeding does not overwrite existing data."""
    seed_dir = tmp_path / "seed"
    (seed_dir / "accounts").mkdir(parents=True)
    (seed_dir / "accounts" / "s3-acct-idem.json").write_text(json.dumps({"name": "S3 Idempotent"}))

    monkeypatch.setenv("REGISTRY_BACKEND", "s3")
    monkeypatch.setenv("REGISTRY_BACKEND_S3_BUCKET", s3_test_bucket)
    monkeypatch.setenv("REGISTRY_SEED_PATH", str(seed_dir))

    s3 = boto3.client("s3")
    key = "registry-v1/accounts/s3-acct-idem.json"

    # 1. Run seeding once to create the object
    app = create_app()
    with TestClient(app):
        obj = s3.get_object(Bucket=s3_test_bucket, Key=key)
        data = json.loads(obj["Body"].read())
        assert data["name"] == "S3 Idempotent"

        # 2. Manually tamper with the object in S3
        s3.put_object(Bucket=s3_test_bucket, Key=key, Body=json.dumps({"name": "TAMPERED"}))

    # 3. Re-create the app to trigger seeding again
    app2 = create_app()
    with TestClient(app2):
        # 4. Verify the tampered object was NOT overwritten
        obj = s3.get_object(Bucket=s3_test_bucket, Key=key)
        data = json.loads(obj["Body"].read())
        assert data["name"] == "TAMPERED"
