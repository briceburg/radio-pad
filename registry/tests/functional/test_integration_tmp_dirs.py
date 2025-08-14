from lib.constants import BASE_DIR


def test_integration_tmp_dirs_layout(functional_tests_root, functional_client):
    """Sanity check: functional tests write under tmp/tests/functional/data and clean up."""
    data_dir = functional_tests_root / "data"
    assert data_dir.parent == BASE_DIR / "tmp" / "tests" / "functional"
    # Directory exists during session (created by functional_client fixture)
    assert data_dir.exists()
