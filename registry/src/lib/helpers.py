import logging
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def get_logger(name=None):
    """Return a logger using the uvicorn.error logger by default.
    Uvicorn's documentation and community recommend using 'uvicorn.error' for application logs and 'uvicorn.access' for HTTP access logs.
    """
    return logging.getLogger(name or "uvicorn.error")


def paginate(items, page=1, per_page=10, max_per_page=100):
    """Paginate a list of items, returning a dict with items and metadata."""
    try:
        page = int(page)
        per_page = int(per_page)
    except (ValueError, TypeError):
        page = 1
        per_page = 10

    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 10
    if per_page > max_per_page:
        per_page = max_per_page

    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    paged_items = items[start:end]
    return {
        "items": paged_items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": (total + per_page - 1) // per_page,
    }
