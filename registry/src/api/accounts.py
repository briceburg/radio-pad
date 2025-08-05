from fastapi import APIRouter

from data.store import store
from models.account import Account
from models.pagination import PaginatedList

router = APIRouter()


@router.get("/accounts", response_model=PaginatedList[Account])
async def list_accounts(page: int = 1, per_page: int = 10):
    """List all accounts"""
    paginated_accounts = store.get_paginated_accounts(page, per_page)
    return PaginatedList(
        items=[
            Account(id=id, name=account.get("name", id.replace("_", " ").title()))
            for id, account in paginated_accounts.items
        ],
        total=paginated_accounts.total,
        page=paginated_accounts.page,
        per_page=paginated_accounts.per_page,
    )
