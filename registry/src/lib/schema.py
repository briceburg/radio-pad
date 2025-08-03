import json

import jsonschema
import referencing.retrieval
from referencing import Registry
from referencing.exceptions import NoSuchResource

from lib.constants import BASE_DIR


class SchemaConstructionError(Exception):
    """Custom exception for schema construction errors."""


@referencing.retrieval.to_cached_resource()
def _retrieve_from_schema_file(uri):
    schema_path = SCHEMA_DIR / uri
    if not schema_path.exists():
        raise NoSuchResource(ref=uri)

    return schema_path.read_text()


SCHEMA_DIR = BASE_DIR / "spec" / "schemas"
SCHEMA_REGISTRY = Registry(retrieve=_retrieve_from_schema_file)


def _construct_item(schema: dict, instance: dict) -> dict:
    """Helper to construct a single dictionary item based on a schema."""
    if not isinstance(instance, dict):
        return instance

    constructed_item = {}
    properties = schema.get("properties", {})

    for prop_name in properties:
        if prop_name in instance:
            constructed_item[prop_name] = instance[prop_name]

    for prop_name in schema.get("required", []):
        if prop_name not in constructed_item:
            prop_schema = properties.get(prop_name, {})
            if "default" in prop_schema:
                constructed_item[prop_name] = prop_schema["default"]

    if schema.get("additionalProperties", True):
        for key, value in instance.items():
            if key not in constructed_item:
                constructed_item[key] = value

    return constructed_item


def construct_from_schema(schema_name: str, instance: dict | list) -> dict | list:
    """Attempt to construct a response that conforms to a given Schema. Returns a valid object or raises SchemaConstructionError."""

    schema_file = f"{schema_name}.json"
    schema_path = SCHEMA_DIR / schema_file

    if not schema_path.exists():
        raise SchemaConstructionError(
            f"Schema file {schema_file} does not exist in {SCHEMA_DIR}."
        )

    try:
        schema_data = json.loads(schema_path.read_text())
        schema = schema_data.get("definitions", {}).get(schema_name, schema_data)

        validator = jsonschema.Draft7Validator(schema, registry=SCHEMA_REGISTRY)

        if validator.is_valid(instance):
            return instance

        if schema.get("type") == "array" and isinstance(instance, list):
            constructed_list = []
            item_schema = schema.get("items", {})
            for item in instance:
                if isinstance(item, dict):
                    constructed_item = _construct_item(item_schema, item)
                    constructed_list.append(constructed_item)
                else:
                    constructed_list.append(item)

            try:
                validator.validate(constructed_list)
                return constructed_list
            except jsonschema.ValidationError as e:
                raise SchemaConstructionError(
                    f"Constructed instance is still invalid: {e.message}"
                )

        elif schema.get("type") == "object" and isinstance(instance, dict):
            constructed_item = _construct_item(schema, instance)
            try:
                validator.validate(constructed_item)
                return constructed_item
            except jsonschema.ValidationError as e:
                raise SchemaConstructionError(
                    f"Constructed instance is still invalid: {e.message}"
                )

        raise SchemaConstructionError(
            "Unable to construct a valid instance from the given data."
        )

    except Exception as e:
        raise SchemaConstructionError(str(e))


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
