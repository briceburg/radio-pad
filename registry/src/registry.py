from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from starlette.responses import RedirectResponse

from api.router import router as api_router
from data.store import DataStore, store


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    if store._store is None:
        store.initialize(DataStore())
    yield


def create_app():
    app = FastAPI(
        lifespan=lifespan, swagger_ui_parameters={"defaultModelsExpandDepth": 0}
    )

    app.include_router(api_router, prefix="/v1")

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse("/docs")

    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
