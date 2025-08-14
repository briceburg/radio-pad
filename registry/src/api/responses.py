from typing import Any

from models import ErrorDetail

# Reusable error response specs
ERROR_404: dict[int | str, dict[str, Any]] = {
    404: {
        "model": ErrorDetail,
        "description": "Not found",
    }
}

ERROR_409: dict[int | str, dict[str, Any]] = {
    409: {
        "model": ErrorDetail,
        "description": "Conflict",
    }
}
