import connexion
from connexion.middleware import MiddlewarePosition
from connexion.options import SwaggerUIOptions
from connexion.resolver import RestyResolver
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse, RedirectResponse

# TODO: write unit tests for response validation
in_unit_test = False

options = SwaggerUIOptions(
    swagger_ui_path="/api-docs",
    swagger_ui_config={
        "displayOperationId": False,
        "defaultModelsExpandDepth": 0,
    },
)

app = connexion.AsyncApp(__name__, specification_dir="spec")
app.add_api(
    "openapi.yaml",
    validate_responses=in_unit_test,
    swagger_ui_options=options,
    resolver=RestyResolver("api"),
)

app.add_middleware(
    CORSMiddleware,
    position=MiddlewarePosition.BEFORE_EXCEPTION,
    allow_origins=["*"],
    allow_credentials=False,
)

app.add_url_rule("/", "root_redirect", lambda req: RedirectResponse("/v1/api-docs/"))
app.add_url_rule("/healthz", "health", lambda req: PlainTextResponse("ok"))

if __name__ == "__main__":
    from pathlib import Path

    app.run(f"{Path(__file__).stem}:app", port=8080)
