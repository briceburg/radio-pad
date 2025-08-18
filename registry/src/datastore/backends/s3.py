import json
from typing import Any, cast

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from datastore.core import (
    compute_etag,
    construct_storage_path,
    deconstruct_storage_path,
    normalize_etag,
    strip_id,
)
from datastore.exceptions import ConcurrencyError
from datastore.types import JsonDoc, PagedResult, ValueWithETag


class S3Backend:
    """S3-backed ObjectStore implementation.

    Notes:
    - Stores documents under keys like: <prefix>/<path...>/<id>.json
    - Stores a content hash in object metadata as 'rpr-sha256' for cheap identity checks.
    - For optimistic concurrency we return/compare backend tokens (VersionId if available else ETag).
    """

    def __init__(self, bucket: str, prefix: str = "", client: BaseClient | None = None) -> None:
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = client or boto3.client("s3")

    def _handle_s3_error(self, error: ClientError, ignore_codes: set[str]) -> None:
        """Re-raises a ClientError unless its code is in the ignore list."""
        code = error.response.get("Error", {}).get("Code")
        if code not in ignore_codes:
            raise error

    def _get_head(self, key: str) -> dict[str, Any] | None:
        try:
            # boto3 client methods are untyped (Any); cast to the expected mapping
            return cast(dict[str, Any], self.client.head_object(Bucket=self.bucket, Key=key))
        except ClientError as e:
            self._handle_s3_error(e, ignore_codes={"404", "NotFound"})
            return None

    def get(self, object_id: str, *path_parts: str) -> ValueWithETag[JsonDoc]:
        key = construct_storage_path(prefix=self.prefix, path_parts=path_parts, object_id=object_id)
        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            self._handle_s3_error(e, ignore_codes={"NoSuchKey", "404", "NotFound"})
            return None, None
        body = resp["Body"].read()
        raw = json.loads(body.decode("utf-8"))
        # compute returned token: prefer VersionId if present
        token = normalize_etag(resp.get("VersionId") or resp.get("ETag"))
        return raw, token

    def list(self, *path_parts: str, page: int = 1, per_page: int = 10) -> PagedResult[JsonDoc]:
        prefix = construct_storage_path(prefix=self.prefix, path_parts=path_parts)
        paginator = self.client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=self.bucket, Prefix=prefix, PaginationConfig={"PageSize": per_page})

        target_page_keys = []
        for i, page_content in enumerate(page_iterator, 1):
            if i == page:
                target_page_keys = [item["Key"] for item in page_content.get("Contents", []) if item.get("Key")]
                break

        items: list[dict[str, Any]] = []
        for k in target_page_keys:
            obj_id, path_parts_from_key = deconstruct_storage_path(k, prefix=self.prefix)
            data, _ = self.get(obj_id, *path_parts_from_key)
            if data is None:
                continue
            data["id"] = obj_id
            items.append(data)

        return items

    def save(self, object_id: str, data: JsonDoc, *path_parts: str, if_match: str | None = None) -> None:
        key = construct_storage_path(prefix=self.prefix, path_parts=path_parts, object_id=object_id)
        to_write = strip_id(data)
        new_hash = compute_etag(to_write)
        head = self._get_head(key)
        current_token = None
        current_hash = None
        if head is not None:
            # HEAD metadata keys are lowercase in boto3
            current_hash = head.get("Metadata", {}).get("rpr-sha256")
            current_token = normalize_etag(head.get("VersionId") or head.get("ETag"))
            # enforce optimistic concurrency
            if if_match is not None and if_match != current_token:
                raise ConcurrencyError("ETag mismatch")
            # no-op if identical content
            if current_hash == new_hash:
                return
        # write
        body = json.dumps(to_write, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body, Metadata={"rpr-sha256": new_hash})

    def delete(self, object_id: str, *path_parts: str) -> bool:
        key = construct_storage_path(prefix=self.prefix, path_parts=path_parts, object_id=object_id)
        # Check existence first to provide consistent semantics with filesystem backend
        head = self._get_head(key)
        if head is None:
            return False
        self.client.delete_object(Bucket=self.bucket, Key=key)
        return True
