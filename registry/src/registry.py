from collections.abc import Sequence

from fastapi import FastAPI


def create_app(profiles: Sequence[str] | None = None) -> FastAPI:
    from api import RegistryAPI

    return RegistryAPI(profiles=profiles)


app = create_app()
