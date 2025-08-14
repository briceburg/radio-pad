import json
from typing import Any, cast

import boto3
import botocore
from botocore.client import BaseClient

from datastore.core import compute_etag, strip_id
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

    def _key_for(self, object_id: str, *path_parts: str) -> str:
        parts = [p for p in path_parts if p]
        if self.prefix:
            parts.insert(0, self.prefix)
        parts.append(f"{object_id}.json")
        return "/".join(parts)

    def _get_head(self, key: str) -> dict[str, Any] | None:
        try:
            # boto3 client methods are untyped (Any); cast to the expected mapping
            return cast(dict[str, Any], self.client.head_object(Bucket=self.bucket, Key=key))
        except botocore.exceptions.ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("404", "NotFound"):
                return None
            raise

    def get(self, object_id: str, *path_parts: str) -> ValueWithETag[JsonDoc]:
        key = self._key_for(object_id, *path_parts)
        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=key)
        except botocore.exceptions.ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404", "NotFound"):
                return None, None
            raise
        body = resp["Body"].read()
        raw = json.loads(body.decode("utf-8"))
        # compute returned token: prefer VersionId if present
        token = resp.get("VersionId") or resp.get("ETag")
        # normalize ETag quotes
        if isinstance(token, str) and token.startswith('"') and token.endswith('"'):
            token = token[1:-1]
        return raw, token

    def list(self, *path_parts: str, page: int = 1, per_page: int = 10) -> PagedResult[JsonDoc]:
        prefix_parts = [p for p in path_parts if p]
        if self.prefix:
            prefix_parts.insert(0, self.prefix)
        prefix = "/".join(prefix_parts)
        if prefix and not prefix.endswith("/"):
            prefix = prefix + "/"
        paginator = self.client.get_paginator("list_objects_v2")
        page_iter = paginator.paginate(Bucket=self.bucket, Prefix=prefix)
        keys: list[str] = []
        for p in page_iter:
            for c in p.get("Contents", []):
                k = c.get("Key")
                if k and k.endswith(".json"):
                    keys.append(k)
        keys.sort()
        total = len(keys)
        start = max(0, (page - 1) * per_page)
        end = start + per_page
        items: list[dict[str, Any]] = []
        for k in keys[start:end]:
            # fetch each object
            obj_id = k.split("/")[-1].rsplit(".json", 1)[0]
            data, _ = self.get(
                obj_id, *(k[len(self.prefix) + 1 :].split("/")[:-1] if self.prefix else k.split("/")[:-1])
            )
            if data is None:
                continue
            data["id"] = obj_id
            items.append(data)
        return items, total

    def save(self, object_id: str, data: JsonDoc, *path_parts: str, if_match: str | None = None) -> None:
        key = self._key_for(object_id, *path_parts)
        to_write = strip_id(data)
        new_hash = compute_etag(to_write)
        head = self._get_head(key)
        current_token = None
        current_hash = None
        if head is not None:
            # HEAD metadata keys are lowercase in boto3
            current_hash = head.get("Metadata", {}).get("rpr-sha256")
            current_token = head.get("VersionId") or head.get("ETag")
            if isinstance(current_token, str) and current_token.startswith('"') and current_token.endswith('"'):
                current_token = current_token[1:-1]
            # enforce optimistic concurrency
            if if_match is not None and if_match != current_token:
                raise ValueError("ETag mismatch")
            # no-op if identical content
            if current_hash == new_hash:
                return None
        # write
        body = json.dumps(to_write, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body, Metadata={"rpr-sha256": new_hash})

    def delete(self, object_id: str, *path_parts: str) -> bool:
        key = self._key_for(object_id, *path_parts)
        # Check existence first to provide consistent semantics with filesystem backend
        head = self._get_head(key)
        if head is None:
            return False
        self.client.delete_object(Bucket=self.bucket, Key=key)
        return True
