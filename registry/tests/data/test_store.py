from data.store import DataStore, get_store


def test_get_store_returns_singleton():
    """Test that get_store returns a singleton instance of the DataStore."""
    store1 = get_store()
    store2 = get_store()
    assert store1 is store2


def test_datastore_loads_station_presets():
    """Test that the DataStore loads station presets correctly."""
    store = DataStore()
    assert len(store.station_presets) > 0
    assert "briceburg" in store.station_presets


def test_datastore_has_accounts_and_players():
    """Test that the DataStore has accounts and players."""
    store = DataStore()
    assert len(store.accounts) > 0
    assert "briceburg" in store.accounts
    assert len(store.players) > 0
    assert "briceburg" in store.players
