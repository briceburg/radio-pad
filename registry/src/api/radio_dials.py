from datastore import DataStore
from lib.types import RadioDialKey
from models import RadioDial, RadioDialSpec, RadioDialSummary, Station

from .exceptions import NotFoundError


def resolve_station_refs(ds: DataStore, spec: RadioDialSpec) -> list[Station]:
    """Resolve Station references with one aggregate read per referenced account."""
    stations, missing = ds.stations.resolve(spec.stations)
    if missing:
        raise NotFoundError(
            "RadioDial references a missing station",
            details={"station_key": missing[0]},
        )
    return stations


def materialize_radio_dial(key: RadioDialKey, spec: RadioDialSpec, stations: list[Station]) -> RadioDial:
    return RadioDial.model_validate({"key": key, **_metadata(spec), "stations": stations})


def summarize_radio_dial(key: RadioDialKey, spec: RadioDialSpec) -> RadioDialSummary:
    return RadioDialSummary.model_validate({"key": key, **_metadata(spec)})


def _metadata(spec: RadioDialSpec) -> dict[str, object]:
    return spec.model_dump(exclude={"stations"})
