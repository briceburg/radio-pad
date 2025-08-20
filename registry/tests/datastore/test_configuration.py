import pytest

from datastore import DataStore
from datastore.backends import LocalBackend, S3Backend


def test_datastore_creates_local_backend_by_default(monkeypatch):
    """By default, with no env vars, a LocalBackend should be created."""
    monkeypatch.delenv("REGISTRY_BACKEND", raising=False)
    monkeypatch.delenv("REGISTRY_BACKEND_PATH", raising=False)

    store = DataStore()
    assert isinstance(store.backend, LocalBackend)


def test_datastore_uses_backend_path_for_local(monkeypatch, tmp_path):
    """A custom path for the LocalBackend can be set via envar."""
    data_dir = tmp_path / "custom_data"
    monkeypatch.setenv("REGISTRY_BACKEND", "local")
    monkeypatch.setenv("REGISTRY_BACKEND_PATH", str(data_dir))

    store = DataStore()
    assert isinstance(store.backend, LocalBackend)
    assert store.backend.base_path == data_dir


def test_datastore_creates_s3_backend_from_env_var(monkeypatch):
    """S3Backend is created when REGISTRY_BACKEND is 's3'."""
    monkeypatch.setenv("REGISTRY_BACKEND", "s3")
    monkeypatch.setenv("REGISTRY_BACKEND_S3_BUCKET", "test-bucket")

    store = DataStore()
    assert isinstance(store.backend, S3Backend)
    assert store.backend.bucket == "test-bucket"


def test_datastore_raises_error_if_s3_bucket_is_missing(monkeypatch):
    """ValueError is raised if S3 is selected but the bucket is not specified."""
    monkeypatch.setenv("REGISTRY_BACKEND", "s3")
    monkeypatch.delenv("REGISTRY_BACKEND_S3_BUCKET", raising=False)

    with pytest.raises(ValueError, match="S3 backend selected but REGISTRY_BACKEND_S3_BUCKET is not set"):
        DataStore()
