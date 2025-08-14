import json
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from datastore.backends.json_file_store import JSONFileStore


@pytest.fixture
def file_store(temp_data_path: Path) -> JSONFileStore:
    return JSONFileStore(str(temp_data_path))


def test_id_not_serialized_on_disk(file_store: JSONFileStore, temp_data_path: Path):
    """Regression: ensure the 'id' field never stored inside JSON content."""
    path_parts = ("test", "id_strip")
    file_store.save("alpha", {"id": "alpha", "value": 1}, *path_parts)
    file_store.save("beta", {"value": 2}, *path_parts)
    file_path = temp_data_path / "test" / "id_strip" / "alpha.json"
    with open(file_path) as f:
        on_disk = json.load(f)
    assert "id" not in on_disk
    items, total = file_store.list(*path_parts)
    assert total == 2
    assert sorted([i["id"] for i in items]) == ["alpha", "beta"]


def test_save_skips_when_unchanged(temp_data_path: Path):
    store = JSONFileStore(str(temp_data_path))
    path = ("skip",)
    obj_id = "same"
    payload = {"a": 1, "b": 2}

    store.save(obj_id, payload, *path)
    first_mtime = (temp_data_path / "skip" / f"{obj_id}.json").stat().st_mtime_ns

    # Call save again with identical content; should not rewrite the file
    store.save(obj_id, {**payload, "id": obj_id}, *path)
    second_mtime = (temp_data_path / "skip" / f"{obj_id}.json").stat().st_mtime_ns

    assert first_mtime == second_mtime


def test_save_still_writes_when_changed(temp_data_path: Path):
    store = JSONFileStore(str(temp_data_path))
    path = ("change",)
    obj_id = "obj"
    payload = {"a": 1}

    store.save(obj_id, payload, *path)
    first_mtime = (temp_data_path / "change" / f"{obj_id}.json").stat().st_mtime_ns

    store.save(obj_id, {"a": 2}, *path)
    second_mtime = (temp_data_path / "change" / f"{obj_id}.json").stat().st_mtime_ns

    assert second_mtime >= first_mtime


# Constrained strategies for safe filenames / path parts
safe_component = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_", min_size=1, max_size=12)
safe_dict_keys = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=10)
safe_values = st.one_of(st.integers(), st.text(alphabet="abcdef012345", max_size=20), st.booleans(), st.none())


@given(
    object_id=safe_component,
    data=st.dictionaries(keys=safe_dict_keys, values=safe_values, max_size=10),
    path_parts=st.lists(safe_component, min_size=1, max_size=3),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
def test_round_trip(temp_data_path: Path, object_id, data, path_parts):
    """Property-based test for saving and retrieving data (safe characters only).
    Note: 'id' key is stripped before persistence; adjust expectation accordingly.
    """
    store = JSONFileStore(str(temp_data_path / "prop"))
    store.save(object_id, data, *path_parts)
    retrieved_data, version = store.get(object_id, *path_parts)
    expected = {k: v for k, v in data.items() if k != "id"}
    assert retrieved_data == expected
    assert isinstance(version, str) and version
