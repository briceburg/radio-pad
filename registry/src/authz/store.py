from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

from auth import AuthenticatedIdentity
from datastore.configuration import AUTHZ_NAMESPACE, authz_backend_from_env
from datastore.core import ExpiringCache, ModelStore, ObjectStore, seed_from_path, seedable
from lib.constants import BASE_DIR

from .models import AccountOwners, SessionRevocations

AUTHZ_DOCUMENT_CACHE_TTL_SECONDS = 5 * 60
_SESSION_REVOCATIONS_ID = "session-revocations"


class AuthzStore:
    def __init__(
        self,
        backend: ObjectStore | None = None,
        *,
        cache_ttl_seconds: float = AUTHZ_DOCUMENT_CACHE_TTL_SECONDS,
        cache_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        seed_root = Path(os.environ.get("REGISTRY_SEED_DATA_PATH", str(BASE_DIR / "seed-data")))
        self.seed_path = seed_root / AUTHZ_NAMESPACE
        self.backend = backend if backend is not None else authz_backend_from_env()
        self._document_cache: ExpiringCache[str, SessionRevocations | None] = ExpiringCache(
            ttl_seconds=cache_ttl_seconds,
            clock=cache_clock,
        )
        self._account_owners: ModelStore[AccountOwners, AccountOwners] = ModelStore(
            self.backend,
            model=AccountOwners,
            path_template="accounts/{id}",
        )
        self._session_revocations: ModelStore[SessionRevocations, SessionRevocations] = ModelStore(
            self.backend,
            model=SessionRevocations,
            path_template="policies/{id}",
        )

    def seed(self) -> None:
        seed_from_path(
            self.seed_path,
            [seedable(self._account_owners), seedable(self._session_revocations)],
            label=AUTHZ_NAMESPACE,
        )

    def check_backend_access(self) -> None:
        self.backend.get("__access_check__", "accounts")

    def get_account_owners(self, account_id: str) -> AccountOwners | None:
        return self._account_owners.get(account_id)

    def save_account_owners(self, owners: AccountOwners) -> AccountOwners:
        return self._account_owners.save(owners)

    def is_account_owner(self, account_id: str, identity: AuthenticatedIdentity) -> bool:
        owners = self.get_account_owners(account_id)
        return owners is not None and owners.allows(identity)

    def get_session_revocations(self) -> SessionRevocations:
        revocations = self._document_cache.get_or_load(
            _SESSION_REVOCATIONS_ID,
            lambda: self._session_revocations.get(_SESSION_REVOCATIONS_ID),
        )
        return revocations or SessionRevocations()

    def save_session_revocations(self, revocations: SessionRevocations) -> SessionRevocations:
        saved = self._session_revocations.save(revocations)
        self._document_cache.invalidate(_SESSION_REVOCATIONS_ID)
        return saved

    def is_session_allowed(self, identity: AuthenticatedIdentity) -> bool:
        return self.get_session_revocations().allows(identity)
