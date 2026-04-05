import os
from pathlib import Path

# API version (GitHub-style date-based versioning)
API_VERSION = "2026-04-30"

# Active service profiles (comma-separated: "api", "switchboard", or both)
PROFILES = [
    profile.strip() for profile in os.getenv("REGISTRY_PROFILES", "api,switchboard").split(",") if profile.strip()
]

# API and WebSocket routing prefixes
API_PREFIX = os.getenv("REGISTRY_API_PREFIX", "/api")
SWITCHBOARD_PREFIX = os.getenv("REGISTRY_SWITCHBOARD_PREFIX", "/switchboard")

# Base URL of the registry API (used by switchboard for remote auth in split mode)
REGISTRY_URL = os.getenv("REGISTRY_URL", f"http://localhost:8000{API_PREFIX}")

# The absolute path to the project root directory
BASE_DIR = Path(__file__).parent.parent.parent

# Slug/ID pattern shared across models and API path params
SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"

# Maximum length for descriptor fields (name, category) - allows for GUID strings
MAX_DESCRIPTOR_LENGTH = 36

# Maximum items per page
MAX_PER_PAGE = 100

# CORS allowed origins (comma-separated)
_DEFAULT_CORS_ORIGINS = (
    "capacitor://localhost,http://localhost:5173,http://localhost:5174,http://localhost,https://localhost"
)
CORS_ORIGINS = [o.strip() for o in os.getenv("REGISTRY_CORS_ORIGINS", _DEFAULT_CORS_ORIGINS).split(",") if o.strip()]
