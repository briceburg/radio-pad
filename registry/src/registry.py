import os

import uvicorn
from fastapi import FastAPI


def create_app() -> FastAPI:
    from api import RegistryAPI

    app = RegistryAPI()
    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.environ.get("REGISTRY_BIND_HOST", "localhost"),
        port=int(os.environ.get("REGISTRY_BIND_PORT", 8000)),
        log_level=os.environ.get("REGISTRY_LOG_LEVEL", "info"),
    )
