def trim_name(value: object) -> str:
    """Normalize a name-like value by trimming surrounding whitespace."""
    if not isinstance(value, str):
        raise ValueError("name must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("name cannot be empty")
    return normalized
