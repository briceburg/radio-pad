from datastore.core import ModelStore, ObjectStore
from models.player import Player, PlayerCreate


class Players(ModelStore[Player, PlayerCreate]):
    """A data store for managing an account's players (accounts/<account_id>/players/<id>.json)."""

    def __init__(self, backend: ObjectStore, create_model: type[PlayerCreate]):
        super().__init__(
            backend,
            model=Player,
            create_model=create_model,
            path_template="accounts/{account_id}/players/{id}",
        )
