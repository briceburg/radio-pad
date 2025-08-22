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
        "registry:app",
        host=os.environ.get("REGISTRY_BIND_HOST", "localhost"),
        log_level=os.environ.get("REGISTRY_LOG_LEVEL", "info"),
        port=int(os.environ.get("REGISTRY_BIND_PORT", 8000)),
        reload=True,
        reload_dirs=["src"],
    )
