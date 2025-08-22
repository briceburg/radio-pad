from pathlib import Path

# The absolute path to the project root directory
BASE_DIR = Path(__file__).parent.parent.parent

# Slug/ID pattern shared across models and API path params
SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"

# Maximum length for descriptor fields (name, category) - allows for GUID strings
MAX_DESCRIPTOR_LENGTH = 36

# Maximum items per page
MAX_PER_PAGE = 100
