def test_list_accounts(client):
    response = client.get("/v1/accounts")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert "items" in data
    assert "page" in data
    assert "per_page" in data
    assert "total" in data
    assert data["total"] == 2
    assert isinstance(data["items"], list)
    for account in data["items"]:
        assert "id" in account
        assert "name" in account


def test_register_account(client):
    """Test that a new account can be created."""
    response = client.put("/v1/accounts/new-account", json={"name": "New Account"})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "new-account"
    assert data["name"] == "New Account"

    # Verify with a GET request
    response = client.get("/v1/accounts")
    data = response.json()
    assert data["total"] == 3
    assert "new-account" in [item["id"] for item in data["items"]]


def test_update_account(client):
    """Test that an existing account can be updated."""
    response = client.put("/v1/accounts/testuser1", json={"name": "Updated Name"})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "testuser1"
    assert data["name"] == "Updated Name"

    # Verify with a GET request
    response = client.get("/v1/accounts")
    data = response.json()
    assert data["total"] == 2
    for item in data["items"]:
        if item["id"] == "testuser1":
            assert item["name"] == "Updated Name"
            break
    else:
        assert False, "testuser1 not found in accounts list"
