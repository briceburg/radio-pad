from __future__ import annotations

import os
from pathlib import Path

from datastore.backends import LocalBackend
from datastore.core import ModelStore, ObjectStore, SeedableStore, seed_from_path, seedable
from lib.constants import BASE_DIR
from lib.logging import logger

from .models import AccountAccess, AuthenticatedIdentity, GlobalAdmins


class AuthzStore:
    def __init__(self, backend: ObjectStore | None = None) -> None:
        seed_root = Path(os.environ.get("REGISTRY_SEED_DATA_PATH", str(BASE_DIR / "seed-data")))
        self.seed_path = seed_root / "auth"
        if backend is None:
            data_path = Path(os.environ.get("REGISTRY_AUTHZ_PATH", str(BASE_DIR / "tmp" / "authz")))
            prefix = os.environ.get("REGISTRY_AUTHZ_PREFIX", "registry-authz-v1")
            logger.info(f"AuthzStore backend: local path={data_path}")
            backend = LocalBackend(base_path=str(data_path), prefix=prefix)

        self.backend = backend
        self._global_admins: ModelStore[GlobalAdmins, GlobalAdmins] = ModelStore(
            self.backend,
            model=GlobalAdmins,
            path_template="{id}",
        )
        self._account_access: ModelStore[AccountAccess, AccountAccess] = ModelStore(
            self.backend,
            model=AccountAccess,
            path_template="accounts/{id}",
        )

    def seed(self) -> None:
        seed_from_path(self.seed_path, self._seedable_stores(), label="authz")

    def get_global_admins(self) -> GlobalAdmins | None:
        return self._global_admins.get("global-admins")

    def save_global_admins(self, admins: GlobalAdmins) -> GlobalAdmins:
        return self._global_admins.save(admins)

    def get_account_access(self, account_id: str) -> AccountAccess | None:
        return self._account_access.get(account_id)

    def save_account_access(self, access: AccountAccess) -> AccountAccess:
        return self._account_access.save(access)

    def is_admin(self, identity: AuthenticatedIdentity) -> bool:
        admins = self.get_global_admins()
        return admins is not None and admins.allows(identity)

    def can_manage_account(self, account_id: str, identity: AuthenticatedIdentity) -> bool:
        if self.is_admin(identity):
            return True
        access = self.get_account_access(account_id)
        return access is not None and access.allows(identity)

    def _seedable_stores(self) -> list[SeedableStore]:
        return [
            seedable(self._global_admins),
            seedable(self._account_access),
        ]
