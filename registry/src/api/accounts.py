from data.store import get_store
from lib.helpers import build_paginated_response

store = get_store()


async def search(page: int = 1, per_page: int = 10):
    """List all accounts - maps to GET /accounts"""

    account_list = [
        {"id": id, "name": account.get("name", id.replace("_", " ").title())}
        for id, account in store.accounts.items()
    ]

    return build_paginated_response(account_list, "AccountList", page, per_page)
