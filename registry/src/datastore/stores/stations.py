from __future__ import annotations

import builtins
from collections.abc import Mapping

from pydantic import TypeAdapter

from datastore.core import ObjectStore
from datastore.types import JsonDoc, PathParams
from lib.keys import join_key, split_key
from lib.types import CallSign, Slug, StationKey
from models.station import Station, StationSpec

_CALL_SIGN_ADAPTER: TypeAdapter[str] = TypeAdapter(CallSign)
_SLUG_ADAPTER: TypeAdapter[str] = TypeAdapter(Slug)


class Stations:
    """Account-owned stations stored at accounts/<account_id>/stations.json."""

    def __init__(self, backend: ObjectStore):
        self._backend = backend

    def get(self, account_id: str, call_sign: str) -> Station | None:
        stations_by_call_sign, _ = self._load(account_id)
        canonical_call_sign = self._canonical_call_sign(call_sign)
        spec = stations_by_call_sign.get(canonical_call_sign)
        if spec is None:
            return None
        return self._station(account_id, canonical_call_sign, spec)

    def list(self, account_id: str, *, page: int = 1, per_page: int = 10) -> builtins.list[Station]:
        stations_by_call_sign, _ = self._load(account_id)
        items = sorted(stations_by_call_sign.items())
        start = max(0, (page - 1) * per_page)
        return [self._station(account_id, call_sign, spec) for call_sign, spec in items[start : start + per_page]]

    def upsert(self, account_id: str, call_sign: str, spec: StationSpec) -> Station:
        stations_by_call_sign, version = self._load(account_id)
        canonical_call_sign = self._canonical_call_sign(call_sign)
        updated = {**stations_by_call_sign, canonical_call_sign: spec}
        self._backend.save(
            "stations",
            self._dump(updated),
            "accounts",
            account_id,
            if_match=version,
            if_none_match=version is None,
        )
        return self._station(account_id, canonical_call_sign, spec)

    def resolve(self, keys: builtins.list[StationKey]) -> tuple[builtins.list[Station], builtins.list[StationKey]]:
        stations_by_account: dict[str, dict[CallSign, StationSpec]] = {}
        resolved: builtins.list[Station] = []
        missing: builtins.list[StationKey] = []

        for key in keys:
            account_id, call_sign = split_key(key)
            if account_id not in stations_by_account:
                stations_by_account[account_id], _ = self._load(account_id)
            spec = stations_by_account[account_id].get(call_sign)
            if spec is None:
                missing.append(key)
                continue
            resolved.append(self._station(account_id, call_sign, spec))

        return resolved, missing

    def match(self, path: str) -> dict[str, str] | None:
        parts = path.split("/")
        if len(parts) == 3 and parts[0] == "accounts" and parts[2] == "stations.json":
            return {"id": "stations", "account_id": parts[1]}
        return None

    def exists(self, object_id: str, *, path_params: Mapping[str, str] | None = None) -> bool:
        account_id = self._account_id(path_params)
        data, _ = self._backend.get("stations", "accounts", account_id)
        return data is not None

    def seed(self, data: JsonDoc, *, path_params: PathParams | None = None) -> None:
        account_id = self._account_id(path_params)
        payload = dict(data)
        if payload.get("id") == "stations":
            payload.pop("id")
        if payload.get("account_id") == account_id:
            payload.pop("account_id")
        stations_by_call_sign = self._parse(payload)
        self._backend.save("stations", self._dump(stations_by_call_sign), "accounts", account_id)

    def _load(self, account_id: str) -> tuple[dict[CallSign, StationSpec], str | None]:
        data, version = self._backend.get("stations", "accounts", account_id)
        return self._parse(data or {}), version

    def _parse(self, data: JsonDoc) -> dict[CallSign, StationSpec]:
        stations: dict[CallSign, StationSpec] = {}
        for raw_call_sign, payload in data.items():
            call_sign = self._canonical_call_sign(raw_call_sign)
            if call_sign in stations:
                raise ValueError(f"Duplicate station call sign: {call_sign}")
            stations[call_sign] = StationSpec.model_validate(payload)
        return stations

    def _dump(self, stations: dict[CallSign, StationSpec]) -> JsonDoc:
        return {call_sign: spec.model_dump(mode="json") for call_sign, spec in stations.items()}

    def _station(self, account_id: str, call_sign: str, spec: StationSpec) -> Station:
        return Station.model_validate(
            {
                "key": join_key(account_id, call_sign),
                "call_sign": call_sign,
                **spec.model_dump(),
            }
        )

    def _canonical_call_sign(self, call_sign: str) -> str:
        return _CALL_SIGN_ADAPTER.validate_python(call_sign)

    def _account_id(self, path_params: Mapping[str, str] | None) -> str:
        if not path_params or not isinstance(path_params.get("account_id"), str):
            raise ValueError("account_id path parameter is required for stations")
        return _SLUG_ADAPTER.validate_python(path_params["account_id"])
