from datastore.core import ModelStore, ObjectStore
from models.account import Account


class Accounts(ModelStore[Account]):
    """A data store for managing accounts (accounts/<id>.json)."""

    def __init__(self, backend: ObjectStore):
        super().__init__(backend, model=Account, path_template="accounts/{id}")
