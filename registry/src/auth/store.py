from __future__ import annotations

import os
from pathlib import Path

from datastore.backends import LocalBackend
from datastore.core import ModelStore, ObjectStore, seed_from_path, seedable
from lib.constants import BASE_DIR
from lib.logging import logger

from .models import AccountOwners, AuthenticatedIdentity


class AuthzStore:
    def __init__(self, backend: ObjectStore | None = None) -> None:
        seed_root = Path(os.environ.get("REGISTRY_SEED_DATA_PATH", str(BASE_DIR / "seed-data")))
        self.seed_path = seed_root / "auth"
        if backend is None:
            data_path = Path(os.environ.get("REGISTRY_AUTHZ_PATH", str(BASE_DIR / "tmp" / "authz")))
            prefix = os.environ.get("REGISTRY_AUTHZ_PREFIX", "registry-authz-v1")
            logger.info("AuthzStore backend: local path=%s", data_path)
            backend = LocalBackend(base_path=str(data_path), prefix=prefix)

        self.backend = backend
        self._account_owners: ModelStore[AccountOwners, AccountOwners] = ModelStore(
            self.backend,
            model=AccountOwners,
            path_template="accounts/{id}",
        )

    def seed(self) -> None:
        seed_from_path(self.seed_path, [seedable(self._account_owners)], label="authz")

    def get_account_owners(self, account_id: str) -> AccountOwners | None:
        return self._account_owners.get(account_id)

    def save_account_owners(self, owners: AccountOwners) -> AccountOwners:
        return self._account_owners.save(owners)

    def is_account_owner(self, account_id: str, identity: AuthenticatedIdentity) -> bool:
        owners = self.get_account_owners(account_id)
        return owners is not None and owners.allows(identity)
