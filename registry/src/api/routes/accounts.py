from fastapi import APIRouter, Depends

from models import Account, AccountSpec

from ..auth import require_account_manager
from ..helpers import get_or_404
from ..models import PaginatedList
from ..responses import ERROR_409
from ..types import DS, AccountId, PageParams

router = APIRouter(prefix="/accounts")


@router.put("/{account_id}", response_model=Account, responses=ERROR_409)
async def register_account(
    account_id: AccountId,
    ds: DS,
    account_spec: AccountSpec,
    _identity: object = Depends(require_account_manager),
) -> Account:
    return ds.accounts.upsert(account_id, account_spec)


@router.get("/{account_id}", response_model=Account)
async def get_account(
    account_id: AccountId,
    ds: DS,
) -> Account:
    return get_or_404(ds.accounts.get(account_id), "Account not found", account_id=account_id)


@router.get("/", response_model=PaginatedList[Account])
async def list_accounts(
    ds: DS,
    paging: PageParams,
) -> PaginatedList[Account]:
    accounts = ds.accounts.list(page=paging.page, per_page=paging.per_page)
    return PaginatedList.from_paged(accounts, page=paging.page, per_page=paging.per_page)
