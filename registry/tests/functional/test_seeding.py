import json

import boto3
import httpx
import pytest
from starlette.testclient import TestClient

from registry import create_app
from tests.functional.conftest import FunctionalTestBed


@pytest.mark.functional
def test_seeded_resources_are_loaded(functional_client: httpx.Client) -> None:
    """Verify default seed data for accounts, players, and global presets loads on startup."""
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
def test_custom_seed_idempotency(functional_test_bed: FunctionalTestBed) -> None:
    """Start app with custom seed dir, verify copy then idempotent on restart."""
    # Create custom seed data
    functional_test_bed.create_seed_account("acct-seeded", "Seeded Account")
    functional_test_bed.create_seed_global_preset("jazz", "Jazz")
    functional_test_bed.configure_env()

    # Create the app to trigger the initial seed
    app = create_app()
    with TestClient(app) as client:
        accounts = client.get("/v1/accounts").json()
        assert any(a["id"] == "acct-seeded" for a in accounts["items"])

        # Tamper with the data to ensure it is not overwritten on next startup
        tampered_path = functional_test_bed.data_dir / "registry-v1" / "accounts" / "acct-seeded.json"
        tampered_path.write_text(json.dumps({"name": "TAMPERED"}))

    # Re-create the app and client to trigger lifespan startup again
    app2 = create_app()
    with TestClient(app2) as client2:
        resp = client2.get("/v1/accounts/acct-seeded")
        assert resp.json()["name"] == "TAMPERED"


@pytest.mark.functional
@pytest.mark.s3
def test_s3_seeding(s3_test_bucket: str, functional_test_bed: FunctionalTestBed) -> None:
    """Verify seeding works with the S3 backend."""
    functional_test_bed.monkeypatch.setenv("REGISTRY_BACKEND", "s3")
    functional_test_bed.monkeypatch.setenv("REGISTRY_BACKEND_S3_BUCKET", s3_test_bucket)
    functional_test_bed.create_seed_account("s3-acct", "S3 Account")
    functional_test_bed.configure_env()

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
def test_s3_seed_idempotency(s3_test_bucket: str, functional_test_bed: FunctionalTestBed) -> None:
    """Verify S3 seeding does not overwrite existing data."""
    functional_test_bed.monkeypatch.setenv("REGISTRY_BACKEND", "s3")
    functional_test_bed.monkeypatch.setenv("REGISTRY_BACKEND_S3_BUCKET", s3_test_bucket)
    functional_test_bed.create_seed_account("s3-acct-idem", "S3 Idempotent")
    functional_test_bed.configure_env()

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
