from data.store import DataStore, store


def test_store_is_singleton_proxy():
    """Test that the global store is a singleton StoreProxy."""
    from data.store import store as store1
    from data.store import store as store2

    assert store1 is store2


def test_datastore_loads_station_presets():
    """Test that the DataStore loads station presets correctly."""
    real_store = DataStore()
    assert len(real_store.presets._presets) > 0
    assert "briceburg" in real_store.presets._presets


def test_datastore_has_accounts_and_players():
    """Test that the DataStore has accounts and players."""
    real_store = DataStore()
    assert len(real_store.accounts._accounts) > 0
    assert "briceburg" in real_store.accounts._accounts
    assert len(real_store.accounts._get_raw_players("briceburg")) > 0
    assert len(real_store.accounts._get_raw_players("otheruser")) > 0


def test_proxy_initialization():
    """Test that the proxy can be initialized and forwards calls."""
    real_store = DataStore()
    store.initialize(real_store)
    assert store.accounts._accounts is real_store.accounts._accounts
