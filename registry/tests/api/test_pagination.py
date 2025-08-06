import pytest


@pytest.mark.parametrize(
    "url,total",
    [
        ("/v1/accounts", 2),
        ("/v1/accounts/testuser1/players", 2),
        ("/v1/presets", 1),
    ],
)
def test_pagination_out_of_bounds(client, url: str, total: int):
    response = client.get(f"{url}?page=1000&per_page=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 0
    assert data["page"] == 1000
    assert data["per_page"] == 1
    assert data["total"] == total


@pytest.mark.parametrize(
    "url,total",
    [
        ("/v1/accounts", 2),
        ("/v1/accounts/testuser1/players", 2),
        ("/v1/presets", 1),
    ],
)
def test_per_page_parameter_works(client, url: str, total: int):
    response = client.get(f"{url}?page=1&per_page={total}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == total
    assert data["page"] == 1
    assert data["per_page"] == total
    assert data["total"] == total

    response = client.get(f"{url}?page=1&per_page={total + 1}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == total
    assert data["page"] == 1
    assert data["per_page"] == total + 1
    assert data["total"] == total


@pytest.mark.parametrize(
    "url,item_id_1,item_id_2,total",
    [
        ("/v1/accounts", "testuser1", "testuser2", 2),
        ("/v1/accounts/testuser1/players", "player1", "player2", 2),
    ],
)
def test_pagination_works(client, url: str, item_id_1: str, item_id_2: str, total: int):
    response = client.get(f"{url}?page=1&per_page=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == item_id_1
    assert data["page"] == 1
    assert data["per_page"] == 1
    assert data["total"] == total

    response = client.get(f"{url}?page=2&per_page=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == item_id_2
    assert data["page"] == 2
    assert data["per_page"] == 1
    assert data["total"] == total
