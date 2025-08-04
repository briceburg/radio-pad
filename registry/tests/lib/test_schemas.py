import pytest

from lib.schema import SchemaConstructionError, construct_from_schema, validate_schema


def test_validate_schema_valid_stationlist():
    """Tests that a valid StationList instance passes validation."""
    instance = [
        {"name": "wwoz", "url": "https://www.wwoz.org/listen/hi"},
        {"name": "wmse", "url": "https://wmse.streamguys1.com/wmselivemp3"},
    ]
    is_valid, err = validate_schema("StationList", instance)
    assert is_valid
    assert err is None


def test_validate_schema_invalid_stationlist_missing_name():
    """Tests that an invalid StationList instance with a missing 'name' fails validation."""
    instance = [
        {"url": "https://www.wwoz.org/listen/hi"},
        {"name": "wmse", "url": "https://wmse.streamguys1.com/wmselivemp3"},
    ]
    is_valid, err = validate_schema("StationList", instance)
    assert not is_valid
    assert "'name' is a required property" in err


def test_validate_schema_invalid_stationlist_missing_url():
    """Tests that an invalid StationList instance with a missing 'url' fails validation."""
    instance = [
        {"name": "wwoz", "url": "https://www.wwoz.org/listen/hi"},
        {"name": "wmse"},
    ]
    is_valid, err = validate_schema("StationList", instance)
    assert not is_valid
    assert "'url' is a required property" in err


def test_validate_schema_file_not_found():
    """Tests that a non-existent schema file fails validation."""
    instance = []
    is_valid, err = validate_schema("NonExistentSchema", instance)
    assert not is_valid
    assert "does not exist" in err


def test_construct_from_schema_invalid_object_raises_exception():
    """Tests that an invalid object instance raises SchemaConstructionError."""
    instance = {"foo": "bar"}
    with pytest.raises(SchemaConstructionError):
        construct_from_schema("Account", instance)


def test_construct_from_schema_invalid_list_raises_exception():
    """Tests that an invalid list instance raises SchemaConstructionError."""
    instance = [{"foo": "bar"}]
    with pytest.raises(SchemaConstructionError):
        construct_from_schema("AccountList", instance)
