import json

import jsonschema
import referencing.retrieval
from referencing import Registry
from referencing.exceptions import NoSuchResource

from lib.helpers import BASE_DIR

SCHEMA_DIR = BASE_DIR / "spec" / "schemas"


def validate_schema(schema_name: str, instance: dict | list) -> tuple[bool, str | None]:
    """Validate a JSON instance against a schema. Returns (is_valid, error_message)."""
    schema_file = f"{schema_name}.json"
    schema_path = SCHEMA_DIR / schema_file

    if not schema_path.exists():
        return False, f"Schema file {schema_file} does not exist in {SCHEMA_DIR}."

    try:
        schema_data = json.loads(schema_path.read_text())
        jsonschema.Draft7Validator(
            schema_data.get("definitions", {}).get(schema_name, schema_data),
            registry=SCHEMA_REGISTRY,
        ).validate(instance)
        return True, None
    except jsonschema.ValidationError as e:
        return False, e.message


@referencing.retrieval.to_cached_resource()
def _retrieve_from_schema_file(uri):
    schema_path = (SCHEMA_DIR / uri).resolve()
    try:
        # Ensure the resolved path is within SCHEMA_DIR
        schema_path.relative_to(SCHEMA_DIR.resolve())
    except ValueError:
        # Path traversal attempt detected
        raise NoSuchResource(ref=uri)
    if not schema_path.exists():
        raise NoSuchResource(ref=uri)

    return schema_path.read_text()


SCHEMA_REGISTRY = Registry(retrieve=_retrieve_from_schema_file)
