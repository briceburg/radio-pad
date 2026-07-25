from __future__ import annotations

import os
from pathlib import Path

from datastore.configuration import AUTHZ_BACKEND_DEFAULTS, DATA_BACKEND_DEFAULTS, build_backend_from_env
from datastore.core import ModelStore, ObjectStore, seed_from_path, seedable
from lib.constants import BASE_DIR

from .models import AccountOwners, AuthenticatedIdentity


class AuthzStore:
    def __init__(self, backend: ObjectStore | None = None) -> None:
        seed_root = Path(os.environ.get("REGISTRY_SEED_DATA_PATH", str(BASE_DIR / "seed-data")))
        self.seed_path = seed_root / "auth"
        if backend is None:
            backend, _prefix = build_backend_from_env(
                "REGISTRY_BACKEND_AUTH",
                AUTHZ_BACKEND_DEFAULTS,
                inherit_from=("REGISTRY_BACKEND", DATA_BACKEND_DEFAULTS),
            )

        self.backend = backend
        self._account_owners: ModelStore[AccountOwners, AccountOwners] = ModelStore(
            self.backend,
            model=AccountOwners,
            path_template="accounts/{id}",
        )

    def seed(self) -> None:
        seed_from_path(self.seed_path, [seedable(self._account_owners)], label="authz")

    def validate_access(self) -> None:
        self._account_owners.list(page=1, per_page=1)

    def get_account_owners(self, account_id: str) -> AccountOwners | None:
        return self._account_owners.get(account_id)

    def save_account_owners(self, owners: AccountOwners) -> AccountOwners:
        data = owners.model_dump(mode="json", exclude={"id"})
        self.backend.save(owners.id, data, "accounts")
        return owners

    def is_account_owner(self, account_id: str, identity: AuthenticatedIdentity) -> bool:
        owners = self.get_account_owners(account_id)
        return owners is not None and owners.allows(identity)
