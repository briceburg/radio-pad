from pydantic import Field

from datastore.core import ModelStore, ObjectStore
from lib.types import Slug
from models.radio_dial import RadioDialSpec


class _RadioDialRecord(RadioDialSpec):
    """Internal datastore entity; API models expose a qualified key instead."""

    id: Slug = Field(..., json_schema_extra={"example": "briceburg"})
    account_id: Slug = Field(..., json_schema_extra={"example": "community"})


class RadioDials(ModelStore[_RadioDialRecord, RadioDialSpec]):
    """Account RadioDials stored at accounts/<account_id>/radio-dials/<id>.json."""

    def __init__(self, backend: ObjectStore):
        super().__init__(backend, model=_RadioDialRecord, path_template="accounts/{account_id}/radio-dials/{id}")
