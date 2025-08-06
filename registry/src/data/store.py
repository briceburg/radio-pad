from typing import List, TypeVar

from models.pagination import PaginatedList

from .stores.account_store import AccountStore
from .stores.station_preset_store import StationPresetStore

T = TypeVar("T")


class DataStore:
    """A container for the application's data stores."""

    def __init__(self):
        self.accounts = AccountStore(self._paginate)
        self.presets = StationPresetStore(self._paginate)

    def _paginate(self, items: List[T], page: int, per_page: int) -> PaginatedList[T]:
        """Paginates a list of items and returns a PaginatedList model instance."""
        total = len(items)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_items = items[start:end]

        return PaginatedList(
            items=paginated_items,
            total=total,
            page=page,
            per_page=per_page,
        )


class StoreProxy:
    """A proxy object that forwards attribute access to the real DataStore."""

    def __init__(self):
        self._store = None

    def initialize(self, store: DataStore):
        """Initializes the proxy with the real DataStore instance."""
        self._store = store

    def __getattr__(self, name):
        if self._store is None:
            raise RuntimeError("DataStore has not been initialized")
        return getattr(self._store, name)


store = StoreProxy()
