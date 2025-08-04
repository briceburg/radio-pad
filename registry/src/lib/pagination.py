from typing import List, TypeVar

from models.pagination import PaginatedList

T = TypeVar("T")


def paginate(items: List[T], page: int, per_page: int) -> PaginatedList[T]:
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
