import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from datastore import DataStore
from lib.constants import BASE_DIR

from .models import ErrorDetail
from .routes import presets_account, presets_global


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Handles application startup and shutdown events."""
    if not hasattr(app.state, "store"):
        ds = DataStore(
            data_path=os.environ.get("REGISTRY_PATH_DATA", str(BASE_DIR / "tmp" / "data")),
            seed_path=os.environ.get("REGISTRY_PATH_SEED", str(BASE_DIR / "data")),
        )
        ds.seed()
        app.state.store = ds  # expose for dependencies
    yield
    # add cleanup logic here


class RegistryAPI(FastAPI):
    def __init__(self) -> None:
        super().__init__(
            lifespan=lifespan,
            swagger_ui_parameters={"defaultModelsExpandDepth": 0},
            redirect_slashes=False,
        )

        from datastore.exceptions import ConcurrencyError

        from .exceptions import NotFoundError
        from .responses import ERROR_404
        from .routes import accounts, players

        router = APIRouter(responses=ERROR_404)
        router.include_router(accounts.router, tags=["accounts"])
        router.include_router(players.router, tags=["players"])
        router.include_router(presets_account.router, tags=["station presets"])
        router.include_router(presets_global.router, tags=["station presets"])
        self.include_router(router, prefix="/v1")

        @self.exception_handler(NotFoundError)
        async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
            err = ErrorDetail(code=exc.code, message=str(exc), details=exc.details)
            return JSONResponse(status_code=404, content=err.model_dump())

        @self.exception_handler(ConcurrencyError)
        async def conflict_handler(request: Request, exc: ConcurrencyError) -> JSONResponse:
            err = ErrorDetail(code="conflict", message=str(exc), details=None)
            return JSONResponse(status_code=409, content=err.model_dump())

        @self.get("/", include_in_schema=False)
        async def root() -> RedirectResponse:
            return RedirectResponse("/docs")

        @self.get("/healthz", include_in_schema=False, status_code=204)
        async def healthz() -> Response:
            # 204 No Content, explicit no-store to avoid caching
            return Response(status_code=204, headers={"Cache-Control": "no-store"})
