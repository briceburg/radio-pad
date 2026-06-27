from datastore.core import ModelStore, ObjectStore
from models.account import Account, AccountSpec


class Accounts(ModelStore[Account, AccountSpec]):
    """A data store for managing accounts (accounts/<id>.json)."""

    def __init__(self, backend: ObjectStore):
        super().__init__(backend, model=Account, path_template="accounts/{id}")
