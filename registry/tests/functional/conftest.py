import json
from collections.abc import Generator
from pathlib import Path

import boto3
import httpx
import pytest
from _pytest.monkeypatch import MonkeyPatch
from starlette.testclient import TestClient

from datastore.types import JsonDoc
from registry import create_app

pytest.importorskip("moto")
from moto import mock_aws


class FunctionalTestBed:
    """Helper for setting up functional tests with custom seed data."""

    def __init__(self, tmp_path: Path, monkeypatch: MonkeyPatch):
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch
        self.seed_dir = self.tmp_path / "seed"
        self.data_dir = self.tmp_path / "data"

    def configure_env(self) -> None:
        self.monkeypatch.setenv("REGISTRY_BACKEND_PATH", str(self.data_dir))
        self.monkeypatch.setenv("REGISTRY_SEED_PATH", str(self.seed_dir))

    def create_seed_account(self, account_id: str, name: str) -> None:
        accounts_dir = self.seed_dir / "accounts"
        accounts_dir.mkdir(parents=True, exist_ok=True)
        (accounts_dir / f"{account_id}.json").write_text(json.dumps({"name": name}))

    def create_seed_global_preset(self, preset_id: str, name: str, stations: list[JsonDoc] | None = None) -> None:
        presets_dir = self.seed_dir / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / f"{preset_id}.json").write_text(json.dumps({"name": name, "stations": stations or []}))


@pytest.fixture(scope="function")
def functional_test_bed(tmp_path: Path, monkeypatch: MonkeyPatch) -> FunctionalTestBed:
    """
    Function-scoped fixture that provides a test bed for creating custom seed data
    and configuring the environment.
    """
    return FunctionalTestBed(tmp_path, monkeypatch)


@pytest.fixture(scope="session")
def functional_client(
    session_monkeypatch: MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[httpx.Client]:
    """
    Session-scoped client that uses the default seed data from `data/`.
    """
    session_monkeypatch.setenv("REGISTRY_BACKEND_PATH", str(tmp_path_factory.mktemp("data-session")))
    # REGISTRY_SEED_PATH is NOT set, so the default `data/` is used.

    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function")
def s3_test_bucket() -> Generator[str]:
    """Creates a mock S3 bucket for testing."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-bucket"
        s3.create_bucket(Bucket=bucket_name)
        yield bucket_name
