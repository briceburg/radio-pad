import connexion
from connexion.middleware import MiddlewarePosition
from connexion.options import SwaggerUIOptions
from connexion.resolver import RestyResolver
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse, RedirectResponse

options = SwaggerUIOptions(swagger_ui_path="/api-docs")

app = connexion.AsyncApp(__name__, specification_dir="spec", swagger_ui_options=options)
app.add_api("openapi.yaml", swagger_ui_options=options, resolver=RestyResolver("api"))

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
