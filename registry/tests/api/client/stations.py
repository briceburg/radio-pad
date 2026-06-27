from starlette.testclient import TestClient

from api.models.pagination import PaginationParams
from datastore.types import JsonDoc
from models import StationSpec
from tests.api._helpers import get_json, put_json


class StationApi:
    def __init__(self, client: TestClient):
        self._client = client

    def put(
        self,
        account_id: str,
        call_sign: str,
        payload: StationSpec,
        expected_status: int = 200,
    ) -> JsonDoc:
        return put_json(
            self._client,
            f"accounts/{account_id}/stations/{call_sign}",
            payload,
            expected=expected_status,
        )

    def get(self, account_id: str, call_sign: str, expected_status: int = 200) -> JsonDoc:
        return get_json(
            self._client,
            f"accounts/{account_id}/stations/{call_sign}",
            expected=expected_status,
        )

    def list(
        self,
        account_id: str,
        expected_status: int = 200,
        params: PaginationParams | None = None,
    ) -> JsonDoc:
        return get_json(
            self._client,
            f"accounts/{account_id}/stations",
            expected=expected_status,
            params=params,
        )
