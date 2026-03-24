from pathlib import Path

from datastore.core import atomic_write_json_file


def test_atomic_write_json_file_pretty_formats_json(tmp_path: Path) -> None:
    target = tmp_path / "example.json"

    atomic_write_json_file(
        target,
        {
            "z": 1,
            "nested": {"b": 2, "a": 1},
            "name": "Briceburg",
        },
    )

    assert target.read_text(encoding="utf-8") == (
        '{\n  "name": "Briceburg",\n  "nested": {\n    "a": 1,\n    "b": 2\n  },\n  "z": 1\n}\n'
    )
