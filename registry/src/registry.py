import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Response, Request
from fastapi.responses import JSONResponse
from starlette.responses import RedirectResponse

from api import router as api_router
from api.errors import NotFoundError
from datastore import DataStore
from datastore.core import ConcurrencyError
from lib import BASE_DIR
from models import ErrorDetail


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Handles application startup and shutdown events."""
    if not hasattr(app.state, "store"):
        ds = DataStore(
            data_path=os.environ.get("DATA_PATH", str(BASE_DIR / "tmp" / "data")),
            seed_path=os.environ.get("SEED_PATH", str(BASE_DIR / "data")),
        )
        ds.seed()
        app.state.store = ds  # expose for dependencies
    yield
    # add cleanup logic here


def create_app() -> FastAPI:
    app = FastAPI(
        lifespan=lifespan,
        swagger_ui_parameters={"defaultModelsExpandDepth": 0},
        redirect_slashes=False,
    )

    # Error handlers
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:  # noqa: F811
        err = ErrorDetail(code=exc.code, message=str(exc), details=exc.details)
        return JSONResponse(status_code=404, content=err.model_dump())

    @app.exception_handler(ConcurrencyError)
    async def conflict_handler(request: Request, exc: ConcurrencyError) -> JSONResponse:  # noqa: F811
        err = ErrorDetail(code="conflict", message=str(exc), details=None)
        return JSONResponse(status_code=409, content=err.model_dump())

    app.include_router(api_router, prefix="/v1")

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse("/docs")

    @app.get("/healthz", include_in_schema=False, status_code=204)
    async def healthz() -> Response:
        # 204 No Content, explicit no-store to avoid caching
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
