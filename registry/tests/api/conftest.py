import pytest
from starlette.testclient import TestClient

from tests.api.client.accounts import AccountApi
from tests.api.client.players import PlayerApi
from tests.api.client.radio_dials import RadioDialApi
from tests.api.client.stations import StationApi


@pytest.fixture
def account_api(client: TestClient) -> AccountApi:
    return AccountApi(client)


@pytest.fixture
def player_api(client: TestClient) -> PlayerApi:
    return PlayerApi(client)


@pytest.fixture
def station_api(client: TestClient) -> StationApi:
    return StationApi(client)


@pytest.fixture
def radio_dial_api(client: TestClient) -> RadioDialApi:
    return RadioDialApi(client)
