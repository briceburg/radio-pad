import json
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from datastore.backends.json_file_store import JSONFileStore


@pytest.fixture
def file_store(temp_data_path: Path) -> JSONFileStore:
    return JSONFileStore(str(temp_data_path))


def test_save_and_get(file_store: JSONFileStore):
    object_id = "test-object"
    data = {"key": "value"}
    path_parts = ("test", "path")
    file_store.save(object_id, data, *path_parts)
    retrieved_data, version = file_store.get(object_id, *path_parts)
    assert retrieved_data == data
    assert isinstance(version, str) and version


def test_get_non_existent(file_store: JSONFileStore):
    retrieved_data, version = file_store.get("non-existent", "test", "path")
    assert retrieved_data is None
    assert version is None


def test_list(file_store: JSONFileStore):
    path_parts = ("test", "list")
    for i in range(15):
        file_store.save(f"obj-{i:02}", {"id": i}, *path_parts)
    items, total = file_store.list(*path_parts, page=1, per_page=10)
    assert total == 15
    assert len(items) == 10
    assert items[0]["id"] == "obj-00"
    assert items[9]["id"] == "obj-09"
    items, total = file_store.list(*path_parts, page=2, per_page=10)
    assert total == 15
    assert len(items) == 5
    assert items[0]["id"] == "obj-10"
    assert items[4]["id"] == "obj-14"


def test_delete(file_store: JSONFileStore):
    object_id = "test-object"
    path_parts = ("test", "delete")
    file_store.save(object_id, {"key": "value"}, *path_parts)
    data, _ = file_store.get(object_id, *path_parts)
    assert data is not None
    deleted = file_store.delete(object_id, *path_parts)
    assert deleted is True
    data2, _ = file_store.get(object_id, *path_parts)
    assert data2 is None


def test_delete_non_existent(file_store: JSONFileStore):
    deleted = file_store.delete("non-existent", "test", "delete")
    assert deleted is False


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


def test_list_deterministic_order(file_store: JSONFileStore):
    path_parts = ("test", "deterministic")
    names = ["b", "a", "c"]
    for n in names:
        file_store.save(n, {"value": n}, *path_parts)
    items_first, _ = file_store.list(*path_parts)
    items_second, _ = file_store.list(*path_parts)
    assert [i["id"] for i in items_first] == [i["id"] for i in items_second] == sorted(names)


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
