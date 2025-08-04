import logging

from lib.schema import SchemaConstructionError, construct_from_schema

# Uvicorn's documentation and community recommend using 'uvicorn.error' for
# application logs and 'uvicorn.access' for HTTP access logs.
logger = logging.getLogger("uvicorn.error")


def _handle_schema_error(e):
    """Log a schema construction error and return a standardized error response."""
    error_message = f"Schema construction error: {e}"
    logger.error(error_message)
    return {"error": error_message}, 500


def build_paginated_response(
    raw_items, schema_name, page=1, per_page=10, max_per_page=100
):
    """Build a paginated and schema-conformant response, handling errors gracefully."""
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

    total = len(raw_items)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_raw_items = raw_items[start:end]

    try:
        constructed_items = construct_from_schema(schema_name, paginated_raw_items)
    except SchemaConstructionError as e:
        return _handle_schema_error(e)

    return {
        "items": constructed_items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": (total + per_page - 1) // per_page,
    }


def build_response(raw_item, schema_name):
    """Build a schema-conformant response, handling errors gracefully."""
    try:
        return construct_from_schema(schema_name, raw_item)
    except SchemaConstructionError as e:
        return _handle_schema_error(e)
