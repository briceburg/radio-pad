from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import boto3
import pytest
from _pytest.fixtures import SubRequest

from api.radio_dials import materialize_radio_dial, resolve_station_refs
from datastore import DataStore
from datastore.core import compute_etag
from datastore.core.interfaces import ObjectStore
from datastore.exceptions import ConcurrencyError
from datastore.types import JsonDoc, ValueWithETag
from models.radio_dial import RadioDialSpec
from models.station import StationSpec


@pytest.fixture(params=["json", "s3", "git"], ids=["json", "s3", "git"])
def object_store(request: SubRequest, tmp_path: Path) -> Generator[ObjectStore]:
    """Parameterized backend fixture providing a compatible ObjectStore.

    - json: LocalBackend rooted at a temporary directory
    - s3: S3Backend with moto-backed S3 bucket (versioning enabled)
    """
    if request.param == "json":
        from datastore.backends.local import LocalBackend

        backend: ObjectStore = LocalBackend(str(tmp_path))
        yield backend
    elif request.param == "s3":
        pytest.importorskip("moto")
        from moto import mock_aws

        from datastore.backends.s3 import S3Backend

        with mock_aws():
            client = boto3.client("s3", region_name="us-east-1")
            bucket = "contract-tests"
            client.create_bucket(Bucket=bucket)
            client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
            backend = S3Backend(bucket=bucket, prefix="contract", client=client)
            yield backend
    else:
        from datastore.backends.git import GitBackend

        backend = GitBackend(
            repo_path=str(tmp_path / "git-store"),
            prefix="contract",
            branch="main",
            fetch_ttl_seconds=0,
            author_name="Tests",
            author_email="tests@example.invalid",
        )
        yield backend


class TestObjectStoreContract:
    def test_round_trip_and_id_strip(self, object_store: ObjectStore) -> None:
        path = ("alpha",)
        object_store.save("a", {"id": "a", "k": 1}, *path)
        raw, token = object_store.get("a", *path)
        assert raw == {"k": 1}
        assert isinstance(token, str) and token

    def test_get_nonexistent_returns_none(self, object_store: ObjectStore) -> None:
        data, token = object_store.get("missing", "nowhere")
        assert data is None and token is None

    def test_list_and_pagination_and_determinism(self, object_store: ObjectStore) -> None:
        path = ("list",)
        for name, val in [("b", 2), ("a", 1), ("c", 3)]:
            object_store.save(name, {"v": val}, *path)

        first = object_store.list(*path, page=1, per_page=2)
        assert sorted([i["id"] for i in first]) == ["a", "b"]
        second = object_store.list(*path, page=2, per_page=2)
        assert [i["id"] for i in second] == ["c"]

        again = object_store.list(*path, page=1, per_page=10)
        assert sorted([i["id"] for i in again]) == ["a", "b", "c"]

    def test_delete_semantics(self, object_store: ObjectStore) -> None:
        path = ("del",)
        object_store.save("z", {"x": 1}, *path)
        assert object_store.delete("z", *path) is True
        assert object_store.delete("z", *path) is False

    def test_noop_when_unchanged_and_changed_updates_token(self, object_store: ObjectStore) -> None:
        path = ("noop",)
        object_store.save("same", {"x": 1}, *path)
        _, v1 = object_store.get("same", *path)
        object_store.save("same", {"id": "same", "x": 1}, *path)
        _, v2 = object_store.get("same", *path)
        assert v2 == v1

        object_store.save("same", {"x": 2}, *path)
        _, v3 = object_store.get("same", *path)
        assert v3 != v2

    def test_conditional_write_preconditions(self, object_store: ObjectStore) -> None:
        path = ("conditional",)
        object_store.save("item", {"value": 1}, *path)
        _, stale_version = object_store.get("item", *path)
        assert stale_version is not None

        with pytest.raises(ConcurrencyError):
            object_store.save("item", {"value": 2}, *path, if_none_match=True)

        object_store.save("item", {"value": 2}, *path)
        with pytest.raises(ConcurrencyError):
            object_store.save("item", {"value": 3}, *path, if_match=stale_version)

    @pytest.mark.parametrize(
        ("object_id", "path", "seed_data", "edited_data"),
        [
            ("seeded", ("accounts",), {"name": "Seeded"}, {"name": "Edited"}),
            (
                "stations",
                ("accounts", "seeded"),
                {"WWOZ": {"stream_url": "https://example.test/seeded"}},
                {"WWOZ": {"stream_url": "https://example.test/edited"}},
            ),
        ],
        ids=["account", "stations"],
    )
    def test_seeding_preserves_existing_edits_across_backends(
        self,
        object_store: ObjectStore,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        object_id: str,
        path: tuple[str, ...],
        seed_data: JsonDoc,
        edited_data: JsonDoc,
    ) -> None:
        seed_root = tmp_path / "seed"
        seed_file = seed_root.joinpath(*path, f"{object_id}.json")
        seed_file.parent.mkdir(parents=True)
        seed_file.write_text(json.dumps(seed_data), encoding="utf-8")
        datastore = DataStore(backend=object_store, seed_path=str(seed_root))
        datastore.seed()
        assert object_store.get(object_id, *path)[0] == seed_data

        object_store.save(object_id, edited_data, *path)
        edited = object_store.get(object_id, *path)
        datastore.seed()
        assert object_store.get(object_id, *path) == edited

        object_store.delete(object_id, *path)
        original_get = object_store.get

        def create_after_missing_read(object_id: str, *path: str) -> ValueWithETag[JsonDoc]:
            missing = original_get(object_id, *path)
            assert missing == (None, None)
            object_store.save(object_id, edited_data, *path)
            return missing

        with monkeypatch.context() as patch:
            patch.setattr(object_store, "get", create_after_missing_read)
            datastore.seed()
        assert object_store.get(object_id, *path)[0] == edited_data

    def test_linked_station_update_changes_resolved_radio_dial_revision(self, object_store: ObjectStore) -> None:
        datastore = DataStore(backend=object_store)
        datastore.stations.upsert(
            "community",
            "WWOZ",
            StationSpec.model_validate({"stream_url": "https://example.test/old"}),
        )
        spec = RadioDialSpec(name="Community", stations=["community/WWOZ"])

        def revision() -> str:
            radio_dial = materialize_radio_dial("community/test", spec, resolve_station_refs(datastore, spec))
            return compute_etag(radio_dial.model_dump(mode="json"))

        initial = revision()
        datastore.stations.upsert(
            "community",
            "WWOZ",
            StationSpec.model_validate({"stream_url": "https://example.test/new"}),
        )

        assert revision() != initial
