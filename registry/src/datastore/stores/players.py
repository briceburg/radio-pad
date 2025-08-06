from datastore.core import ModelStore, ObjectStore
from models.player import Player


class Players(ModelStore[Player]):
    """A data store for managing an account's players (accounts/<account_id>/players/<id>.json)."""

    def __init__(self, backend: ObjectStore):
        super().__init__(
            backend,
            model=Player,
            path_template="accounts/{account_id}/players/{id}",
        )
