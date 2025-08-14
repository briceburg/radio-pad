import boto3
import pytest

from datastore import DataStore

pytest.importorskip("moto")
from moto import mock_aws  # type: ignore


@pytest.fixture()
def s3_env(monkeypatch):
    monkeypatch.setenv("REGISTRY_BACKEND", "s3")
    monkeypatch.setenv("REGISTRY_BACKEND_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("REGISTRY_BACKEND_S3_PREFIX", "it")
    yield


def test_s3_save_noop_with_versioning_keeps_version_id(s3_env):
    # Functional/integration: use DataStore (env-configured) and moto to simulate S3
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        # Enable bucket versioning so VersionId is returned and changes on PUT
        s3.put_bucket_versioning(Bucket="test-bucket", VersioningConfiguration={"Status": "Enabled"})

        ds = DataStore()
        backend = ds.backend

        # Initial write
        backend.save("alpha", {"x": 1}, "no-op")
        _, v1 = backend.get("alpha", "no-op")
        assert isinstance(v1, str) and v1

        # Second write with identical content should be a no-op (no PUT), VersionId unchanged
        backend.save("alpha", {"id": "alpha", "x": 1}, "no-op")
        _, v2 = backend.get("alpha", "no-op")
        assert v2 == v1

        # Changed content should trigger a new PUT and new VersionId
        backend.save("alpha", {"x": 2}, "no-op")
        _, v3 = backend.get("alpha", "no-op")
        assert v3 != v2
