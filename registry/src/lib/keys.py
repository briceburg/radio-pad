def normalize_call_sign(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Call sign must be a string")
    return value.strip().upper()


def split_key(value: object) -> tuple[str, str]:
    """Split an account-qualified domain key into its two components."""
    if not isinstance(value, str):
        raise ValueError("Key must be a string")
    normalized = value.strip()
    parts = normalized.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("Key must be in '<account_id>/<local_id>' format")
    return parts[0], parts[1]


def join_key(account_id: str, local_id: str) -> str:
    """Join an account ID and account-local ID into a qualified domain key."""
    return f"{account_id}/{local_id}"
