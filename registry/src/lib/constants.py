from pathlib import Path

# The absolute path to the project root directory
BASE_DIR = Path(__file__).parent.parent.parent

# Slug pattern shared across models and API path params
SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"

__all__ = ["BASE_DIR", "SLUG_PATTERN"]
