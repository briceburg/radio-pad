from models import ErrorDetail

# Reusable error response specs
ERROR_404 = {
    404: {
        "model": ErrorDetail,
        "description": "Not found",
    }
}

ERROR_409 = {
    409: {
        "model": ErrorDetail,
        "description": "Conflict",
    }
}
