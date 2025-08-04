def test_list_accounts(client):
    response = client.get("/v1/accounts")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert "items" in data
    assert "page" in data
    assert "per_page" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    for account in data["items"]:
        assert "id" in account
        assert "name" in account
