from datastore import DataStore
from models import AccountSpec

from .exceptions import NotFoundError


def get_or_404[T](item: T | None, message: str = "Resource not found", **details: str) -> T:
    if item is None:
        raise NotFoundError(message, details=details)
    return item


def ensure_account(ds: DataStore, account_id: str) -> None:
    """Create the owning account on its first account-scoped write."""
    if not ds.accounts.exists(account_id):
        ds.accounts.upsert(account_id, AccountSpec(name=account_id))
