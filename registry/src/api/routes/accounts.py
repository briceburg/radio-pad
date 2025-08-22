from fastapi import APIRouter

from models import Account, AccountCreate, AccountSummary

from ..exceptions import NotFoundError
from ..models import PaginatedList
from ..responses import ERROR_409
from ..types import DS, AccountId, PageParams

router = APIRouter(prefix="/accounts")


@router.put("/{account_id}", response_model=Account, responses=ERROR_409)
async def register_account(
    account_id: AccountId,
    ds: DS,
    account_data: AccountCreate,
) -> Account:
    account = ds.accounts.merge_upsert(account_id, account_data)
    return account


@router.get("/{account_id}", response_model=Account)
async def get_account(
    account_id: AccountId,
    ds: DS,
) -> Account:
    account = ds.accounts.get(account_id)
    if account is None:
        raise NotFoundError("Account not found", details={"account_id": account_id})
    return account


@router.get("/", response_model=PaginatedList[AccountSummary])
async def list_accounts(
    ds: DS,
    paging: PageParams,
) -> PaginatedList[AccountSummary]:
    items = ds.accounts.list(page=paging.page, per_page=paging.per_page)
    summary_items = [_to_summary(account) for account in items]
    return PaginatedList.from_paged(summary_items, page=paging.page, per_page=paging.per_page)


def _to_summary(account: Account) -> AccountSummary:
    return AccountSummary(id=account.id, name=account.name)
