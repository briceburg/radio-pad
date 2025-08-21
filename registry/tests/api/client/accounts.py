from starlette.testclient import TestClient

from api.models.pagination import PaginationParams
from datastore.types import JsonDoc
from models.account import AccountCreate
from tests.api._helpers import get_json, put_json


class AccountApi:
    def __init__(self, client: TestClient):
        self._client = client

    def put(self, account_id: str, payload: AccountCreate, expected_status: int = 200) -> JsonDoc:
        return put_json(
            self._client,
            f"/v1/accounts/{account_id}",
            payload,
            expected=expected_status,
        )

    def get(self, account_id: str, expected_status: int = 200) -> JsonDoc:
        return get_json(
            self._client,
            f"/v1/accounts/{account_id}",
            expected=expected_status,
        )

    def list(self, expected_status: int = 200, params: PaginationParams | None = None) -> JsonDoc:
        return get_json(
            self._client,
            "/v1/accounts",
            expected=expected_status,
            params=params,
        )
