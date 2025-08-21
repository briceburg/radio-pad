import pytest
from starlette.testclient import TestClient

from tests.api.client.accounts import AccountApi
from tests.api.client.players import PlayerApi
from tests.api.client.presets import PresetApi


@pytest.fixture
def account_api(client: TestClient) -> AccountApi:
    return AccountApi(client)


@pytest.fixture
def player_api(client: TestClient) -> PlayerApi:
    return PlayerApi(client)


@pytest.fixture
def preset_api(client: TestClient) -> PresetApi:
    return PresetApi(client)
