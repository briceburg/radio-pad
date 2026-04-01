from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from datastore.backends import LocalBackend
from datastore.types import JsonDoc

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
