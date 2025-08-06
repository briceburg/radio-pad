from fastapi import APIRouter

from data.store import store
from models.account import Account, AccountCreate
from models.pagination import PaginatedList

router = APIRouter()


@router.put("/accounts/{id}", response_model=Account)
async def register_account(id: str, account_data: AccountCreate):
    """Register an account"""
    account_dict = account_data.model_dump(exclude_unset=True)
    account = store.register_account(id, account_dict)

    return Account(id=id, name=account.get("name", id.replace("_", " ").title()))


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
