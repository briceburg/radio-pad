from __future__ import annotations

import boto3
import pytest


@pytest.fixture(params=["json", "s3"], ids=["json", "s3"])
def object_store(request, tmp_path):
    """Parameterized backend fixture providing a compatible ObjectStore.

    - json: LocalBackend rooted at a temporary directory
    - s3: S3Backend with moto-backed S3 bucket (versioning enabled)
    """
    if request.param == "json":
        from datastore.backends.local import LocalBackend

        backend = LocalBackend(str(tmp_path))
        yield backend
    else:
        pytest.importorskip("moto")
        from moto import mock_aws  # type: ignore

        from datastore.backends.s3 import S3Backend

        with mock_aws():
            client = boto3.client("s3", region_name="us-east-1")
            bucket = "contract-tests"
            client.create_bucket(Bucket=bucket)
            client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
            backend = S3Backend(bucket=bucket, prefix="contract", client=client)
            yield backend


def test_contract_round_trip_and_id_strip(object_store):
    path = ("alpha",)
    object_store.save("a", {"id": "a", "k": 1}, *path)
    raw, token = object_store.get("a", *path)
    assert raw == {"k": 1}
    assert isinstance(token, str) and token


def test_contract_get_nonexistent_returns_none(object_store):
    data, token = object_store.get("missing", "nowhere")
    assert data is None and token is None


def test_contract_list_and_pagination_and_determinism(object_store):
    path = ("list",)
    for name, val in [("b", 2), ("a", 1), ("c", 3)]:
        object_store.save(name, {"v": val}, *path)

    first = object_store.list(*path, page=1, per_page=2)
    assert sorted([i["id"] for i in first]) == ["a", "b"]
    second = object_store.list(*path, page=2, per_page=2)
    assert [i["id"] for i in second] == ["c"]

    again = object_store.list(*path, page=1, per_page=10)
    assert sorted([i["id"] for i in again]) == ["a", "b", "c"]


def test_contract_delete_semantics(object_store):
    path = ("del",)
    object_store.save("z", {"x": 1}, *path)
    assert object_store.delete("z", *path) is True
    assert object_store.delete("z", *path) is False


def test_contract_noop_when_unchanged_and_changed_updates_token(object_store):
    path = ("noop",)
    object_store.save("same", {"x": 1}, *path)
    _, v1 = object_store.get("same", *path)
    object_store.save("same", {"id": "same", "x": 1}, *path)
    _, v2 = object_store.get("same", *path)
    assert v2 == v1

    object_store.save("same", {"x": 2}, *path)
    _, v3 = object_store.get("same", *path)
    assert v3 != v2
