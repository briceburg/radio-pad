import pytest
from starlette.testclient import TestClient

from registry import create_app


@pytest.fixture
def client():
    app = create_app(in_unit_test=True)
    with TestClient(app) as client:
        yield client


def test_swagger_ui_renders(client):
    response = client.get("/v1/api-docs")
    assert response.status_code == 200


def test_openapi_json_renders(client):
    response = client.get("/v1/openapi.json")
    assert response.status_code == 200
