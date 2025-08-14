from pathlib import Path

from datastore.backends.json_file_store import JSONFileStore


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
