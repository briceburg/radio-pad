from types import MappingProxyType

from lib.helpers import build_paginated_response


async def search(page: int = 1, per_page: int = 10):
    """List all accounts - maps to GET /accounts"""

    account_list = [
        {"id": id, "name": account.get("name", id.replace("_", " ").title())}
        for id, account in ACCOUNTS.items()
    ]

    return build_paginated_response(account_list, "AccountList", page, per_page)


def _load_accounts():
    accounts = {"briceburg": {}}
    return MappingProxyType(accounts)


ACCOUNTS = _load_accounts()
