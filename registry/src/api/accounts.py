from fastapi import APIRouter

from data.store import store
from lib.pagination import paginate
from models.account import Account
from models.pagination import PaginatedList

router = APIRouter()


@router.get("/accounts", response_model=PaginatedList[Account])
async def list_accounts(page: int = 1, per_page: int = 10):
    """List all accounts"""
    account_list = [
        Account(id=id, name=account.get("name", id.replace("_", " ").title()))
        for id, account in store.accounts.items()
    ]

    return paginate(account_list, page, per_page)
