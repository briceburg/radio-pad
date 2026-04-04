from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from datastore import DataStore
from lib.logging import silence_access_logs
from switchboard.broadcast import Broadcast

from .auth import AuthServices
from .models import ErrorDetail


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Handles application startup and shutdown events."""
    from lib.constants import PROFILES as profiles

    if "api" in profiles:
        if not hasattr(app.state, "store"):
            ds = DataStore()
            ds.seed()
            app.state.store = ds  # expose for dependencies
        if not hasattr(app.state, "auth"):
            app.state.auth = AuthServices.from_env()

    broadcast: Broadcast | None = None
    http_client = None
    if "switchboard" in profiles:
        import httpx

        http_client = httpx.AsyncClient(timeout=5.0)
        app.state.http_client = http_client

        broadcast = Broadcast()
        await broadcast.connect()
        app.state.broadcast = broadcast

    yield

    if broadcast:
        await broadcast.disconnect()
    if http_client:
        await http_client.aclose()


class RegistryAPI(FastAPI):
    def __init__(self) -> None:
        super().__init__(
            lifespan=lifespan,
            swagger_ui_parameters={"defaultModelsExpandDepth": 0},
            redirect_slashes=True,
        )

        from datastore.exceptions import ConcurrencyError
        from lib.constants import CORS_ORIGINS as cors_origins
        from lib.constants import PROFILES as profiles

        from .exceptions import NotFoundError
        from .responses import ERROR_404

        if "api" in profiles:
            from lib.constants import API_PREFIX

            from .routes import accounts, players, presets_account, presets_global

            router = APIRouter(responses=ERROR_404)
            router.include_router(accounts.router, tags=["accounts"])
            router.include_router(players.router, tags=["players"])
            router.include_router(presets_account.router, tags=["station presets"])
            router.include_router(presets_global.router, tags=["station presets"])
            self.include_router(router, prefix=API_PREFIX)

        if "switchboard" in profiles:
            from lib.constants import SWITCHBOARD_PREFIX
            from switchboard import switchboard as switchboard_routes

            # Assuming clients connect to /switchboard/{account_id}/{player_id}
            self.include_router(switchboard_routes.router, prefix=SWITCHBOARD_PREFIX)

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

        from collections.abc import Awaitable, Callable

        from lib.constants import API_VERSION

        @self.middleware("http")
        async def add_api_version_header(
            request: Request, call_next: Callable[[Request], Awaitable[Response]]
        ) -> Response:
            response = await call_next(request)
            response.headers["X-RadioPad-Api-Version"] = API_VERSION
            return response

        silence_access_logs("/healthz")

        self.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
