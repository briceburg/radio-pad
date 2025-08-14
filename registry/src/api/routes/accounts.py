from fastapi import APIRouter

from api.dependencies import DS, AccountId, PageParams
from api.errors import NotFoundError
from api.responses import ERROR_404, ERROR_409
from models import Account, AccountCreate, PaginatedList

router = APIRouter(prefix="/accounts", responses=ERROR_404)


@router.put("/{account_id}", response_model=Account, responses=ERROR_409)
async def register_account(
    account_id: AccountId,
    ds: DS,
    account_data: AccountCreate | None = None,
) -> Account:
    partial = account_data.model_dump(exclude_unset=True) if account_data else {}
    account = ds.accounts.merge_upsert(account_id, partial)
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


@router.get("", response_model=PaginatedList[Account], include_in_schema=False)
@router.get("/", response_model=PaginatedList[Account])
async def list_accounts(
    ds: DS,
    paging: PageParams,
) -> PaginatedList[Account]:
    pl = ds.accounts.list(page=paging.page, per_page=paging.per_page)
    return pl
