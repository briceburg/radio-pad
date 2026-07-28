import os
import secrets
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from auth import SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS
from datastore import DataStore
from lib.constants import API_PREFIX
from lib.logging import silence_access_logs
from switchboard.broadcast import Broadcast

from .auth import AuthServices
from .models import ErrorDetail


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Handles application startup and shutdown events."""
    profiles = app.state.profiles
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
        import httpx2

        http_client = httpx2.AsyncClient(timeout=5.0)
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
    def __init__(self, profiles: Sequence[str] | None = None) -> None:
        super().__init__(
            lifespan=lifespan,
            swagger_ui_parameters={"defaultModelsExpandDepth": 0},
            redirect_slashes=True,
        )
        if profiles is None:
            from lib.constants import PROFILES

            profiles = PROFILES
        self.state.profiles = tuple(profiles)
        self._register_routes()
        self._register_exception_handlers()
        self._register_middleware()

    def _register_routes(self) -> None:
        profiles = self.state.profiles
        if "api" in profiles:
            from lib.constants import API_PREFIX

            from .responses import ERROR_404
            from .routes import accounts, auth, players, radio_dials, stations

            router = APIRouter(responses=ERROR_404)
            router.include_router(auth.router, tags=["auth"])
            router.include_router(accounts.router, tags=["accounts"])
            router.include_router(players.router, tags=["players"])
            router.include_router(stations.router, tags=["stations"])
            router.include_router(radio_dials.router, tags=["radio dials"])
            self.include_router(router, prefix=API_PREFIX)

        if "switchboard" in profiles:
            from lib.constants import SWITCHBOARD_PREFIX
            from switchboard import switchboard as switchboard_routes

            self.include_router(switchboard_routes.router, prefix=SWITCHBOARD_PREFIX)

        @self.get("/", include_in_schema=False)
        async def root() -> RedirectResponse:
            return RedirectResponse("/docs")

        @self.get("/healthz", include_in_schema=False, status_code=204)
        async def healthz() -> Response:
            return Response(status_code=204, headers={"Cache-Control": "no-store"})

    def _register_exception_handlers(self) -> None:
        from datastore.exceptions import ConcurrencyError

        from .exceptions import NotFoundError

        @self.exception_handler(NotFoundError)
        async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
            err = ErrorDetail(code=exc.code, message=str(exc), details=exc.details)
            return JSONResponse(status_code=404, content=err.model_dump())

        @self.exception_handler(ConcurrencyError)
        async def conflict_handler(request: Request, exc: ConcurrencyError) -> JSONResponse:
            err = ErrorDetail(code="conflict", message=str(exc), details=None)
            return JSONResponse(status_code=409, content=err.model_dump())

    def _register_middleware(self) -> None:
        from collections.abc import Awaitable, Callable

        from lib.constants import API_VERSION
        from lib.constants import CORS_ORIGINS as cors_origins

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
        if "api" in self.state.profiles:
            self.add_middleware(
                SessionMiddleware,
                secret_key=os.environ.get("REGISTRY_AUTH_SESSION_SECRET") or secrets.token_urlsafe(32),
                session_cookie=SESSION_COOKIE_NAME,
                max_age=SESSION_MAX_AGE_SECONDS,
                path=f"{API_PREFIX.rstrip('/')}/auth/session",
                same_site="none",
                https_only=True,
            )
