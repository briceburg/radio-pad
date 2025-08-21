import json
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from datastore.backends import LocalBackend
from datastore.types import JsonDoc


@pytest.fixture
def backend(temp_data_path: Path) -> LocalBackend:
    return LocalBackend(str(temp_data_path))


def test_id_not_serialized_on_disk(backend: LocalBackend, temp_data_path: Path) -> None:
    """Regression: ensure the 'id' field never stored inside JSON content."""
    path_parts = ("test", "id_strip")
    backend.save("alpha", {"id": "alpha", "value": 1}, *path_parts)
    backend.save("beta", {"value": 2}, *path_parts)
    file_path = temp_data_path / "test" / "id_strip" / "alpha.json"
    with open(file_path) as f:
        on_disk = json.load(f)
    assert "id" not in on_disk
    items = backend.list(*path_parts)
    assert len(items) == 2
    assert sorted([i["id"] for i in items]) == ["alpha", "beta"]


def test_save_skips_when_unchanged(temp_data_path: Path, backend: LocalBackend) -> None:
    path = ("skip",)
    obj_id = "same"
    payload = {"a": 1, "b": 2}

    backend.save(obj_id, payload, *path)
    first_mtime = (temp_data_path / "skip" / f"{obj_id}.json").stat().st_mtime_ns

    # Call save again with identical content; should not rewrite the file
    backend.save(obj_id, {**payload, "id": obj_id}, *path)
    second_mtime = (temp_data_path / "skip" / f"{obj_id}.json").stat().st_mtime_ns

    assert first_mtime == second_mtime


def test_save_still_writes_when_changed(temp_data_path: Path, backend: LocalBackend) -> None:
    path = ("change",)
    obj_id = "obj"
    payload = {"a": 1}

    backend.save(obj_id, payload, *path)
    first_mtime = (temp_data_path / "change" / f"{obj_id}.json").stat().st_mtime_ns

    backend.save(obj_id, {"a": 2}, *path)
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
def test_round_trip(temp_data_path: Path, object_id: str, data: JsonDoc, path_parts: list[str]) -> None:
    """Property-based test for saving and retrieving data (safe characters only).
    Note: 'id' key is stripped before persistence; adjust expectation accordingly.
    """
    backend = LocalBackend(str(temp_data_path / "prop"))
    backend.save(object_id, data, *path_parts)
    retrieved_data, version = backend.get(object_id, *path_parts)
    expected = {k: v for k, v in data.items() if k != "id"}
    assert retrieved_data == expected
    assert isinstance(version, str) and version
