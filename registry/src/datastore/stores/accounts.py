from datastore.core import ModelStore, ObjectStore
from models.account import Account, AccountCreate


class Accounts(ModelStore[Account, AccountCreate]):
    """A data store for managing accounts (accounts/<id>.json)."""

    def __init__(self, backend: ObjectStore, create_model: type[AccountCreate]):
        super().__init__(backend, model=Account, create_model=create_model, path_template="accounts/{id}")
