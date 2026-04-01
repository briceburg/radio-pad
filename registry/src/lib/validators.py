def trim_name(value: object) -> str:
    """Normalize a name-like value by trimming surrounding whitespace."""
    normalized = str(value).strip()
    if not normalized:
        raise ValueError("name cannot be empty")
    return normalized
