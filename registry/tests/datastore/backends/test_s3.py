from __future__ import annotations

import io
import json
from typing import Any

import boto3
import botocore
import pytest
from botocore.stub import ANY, Stubber

from datastore.backends import S3Backend


def _json_body(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")


def test_save_new_then_get_roundtrip_minimal():
    """Slimmed version to keep S3-specific path (HEAD 404 -> PUT -> GET token)."""
    client = boto3.client("s3", region_name="us-east-1")
    backend = S3Backend(bucket="b", prefix="p", client=client)
    with Stubber(client) as stub:
        stub.add_client_error(
            "head_object",
            service_error_code="404",
            service_message="not found",
            http_status_code=404,
            expected_params={"Bucket": "b", "Key": "p/a.json"},
        )
        expected_payload = {"x": 1}
        stub.add_response(
            "put_object",
            service_response={"ETag": '"etag"'},
            expected_params={
                "Bucket": "b",
                "Key": "p/a.json",
                "Body": _json_body(expected_payload),
                "Metadata": ANY,
            },
        )
        backend.save("a", {"id": "a", **expected_payload}, "")
        stub.add_response(
            "get_object",
            service_response={
                "Body": botocore.response.StreamingBody(
                    raw_stream=io.BytesIO(_json_body(expected_payload)),
                    content_length=len(_json_body(expected_payload)),
                ),
                "ETag": '"etag"',
                "VersionId": "v1",
            },
            expected_params={"Bucket": "b", "Key": "p/a.json"},
        )
        val, token = backend.get("a", "")
        assert val == expected_payload and token == "v1"


def test_save_noop_when_content_hash_matches():
    from datastore.core import compute_etag

    client = boto3.client("s3", region_name="us-east-1")
    backend = S3Backend(bucket="b", prefix="p", client=client)
    payload = {"x": 1}

    expected_hash = compute_etag(payload)

    with Stubber(client) as stub:
        stub.add_response(
            "head_object",
            service_response={
                "ETag": '"e1"',
                "Metadata": {"rpr-sha256": expected_hash},
            },
            expected_params={"Bucket": "b", "Key": "p/a.json"},
        )
        backend.save("a", payload, "")


def test_save_if_match_mismatch_raises():
    client = boto3.client("s3", region_name="us-east-1")
    backend = S3Backend(bucket="b", prefix="p", client=client)
    with Stubber(client) as stub:
        stub.add_response(
            "head_object",
            service_response={"ETag": '"e1"', "VersionId": "v1", "Metadata": {}},
            expected_params={"Bucket": "b", "Key": "p/a.json"},
        )
        with pytest.raises(ValueError):
            backend.save("a", {"x": 2}, "", if_match="v2")


def test_list_returns_items_and_total():
    client = boto3.client("s3", region_name="us-east-1")
    backend = S3Backend(bucket="b", prefix="x", client=client)
    with Stubber(client) as stub:
        stub.add_response(
            "list_objects_v2",
            service_response={
                "IsTruncated": False,
                "KeyCount": 3,
                "Contents": [
                    {"Key": "x/y/a.json"},
                    {"Key": "x/y/b.json"},
                    {"Key": "x/y/c.json"},
                ],
            },
            expected_params={"Bucket": "b", "Prefix": "x/y/"},
        )
        stub.add_response(
            "get_object",
            service_response={
                "Body": botocore.response.StreamingBody(raw_stream=io.BytesIO(_json_body({"v": 1})), content_length=7),
                "ETag": '"e1"',
            },
            expected_params={"Bucket": "b", "Key": "x/y/a.json"},
        )
        stub.add_response(
            "get_object",
            service_response={
                "Body": botocore.response.StreamingBody(raw_stream=io.BytesIO(_json_body({"v": 2})), content_length=7),
                "ETag": '"e2"',
            },
            expected_params={"Bucket": "b", "Key": "x/y/b.json"},
        )
        items, total = backend.list("y", page=1, per_page=2)
        assert total == 3
        assert len(items) == 2
        assert items[0]["id"] == "a" and items[0]["v"] == 1
        assert items[1]["id"] == "b" and items[1]["v"] == 2


def test_delete_success_and_not_found():
    client = boto3.client("s3", region_name="us-east-1")
    backend = S3Backend(bucket="b", prefix="p", client=client)
    with Stubber(client) as stub:
        stub.add_response(
            "head_object", service_response={"ETag": '"e"'}, expected_params={"Bucket": "b", "Key": "p/a.json"}
        )
        stub.add_response("delete_object", service_response={}, expected_params={"Bucket": "b", "Key": "p/a.json"})
        assert backend.delete("a", "") is True
        stub.add_client_error(
            "head_object",
            service_error_code="404",
            service_message="nf",
            http_status_code=404,
            expected_params={"Bucket": "b", "Key": "p/b.json"},
        )
        assert backend.delete("b", "") is False


def test_get_uses_etag_when_version_missing():
    client = boto3.client("s3", region_name="us-east-1")
    backend = S3Backend(bucket="b", prefix="p", client=client)
    with Stubber(client) as stub:
        payload = {"y": 7}
        stub.add_response(
            "get_object",
            service_response={
                "Body": botocore.response.StreamingBody(
                    raw_stream=io.BytesIO(_json_body(payload)), content_length=len(_json_body(payload))
                ),
                "ETag": '"abc123"',
            },
            expected_params={"Bucket": "b", "Key": "p/a.json"},
        )
        data, token = backend.get("a", "")
        assert data == payload
        assert token == "abc123"


def test_save_if_match_success_puts():
    client = boto3.client("s3", region_name="us-east-1")
    backend = S3Backend(bucket="b", prefix="p", client=client)
    with Stubber(client) as stub:
        stub.add_response(
            "head_object",
            service_response={"VersionId": "v1", "ETag": '"e1"', "Metadata": {}},
            expected_params={"Bucket": "b", "Key": "p/a.json"},
        )
        expected_payload = {"k": 1}
        stub.add_response(
            "put_object",
            service_response={"ETag": '"e2"'},
            expected_params={
                "Bucket": "b",
                "Key": "p/a.json",
                "Body": _json_body(expected_payload),
                "Metadata": ANY,
            },
        )
        backend.save("a", {"id": "a", **expected_payload}, "", if_match="v1")


def test_save_changed_content_triggers_put():
    client = boto3.client("s3", region_name="us-east-1")
    backend = S3Backend(bucket="b", prefix="p", client=client)
    with Stubber(client) as stub:
        stub.add_response(
            "head_object",
            service_response={"ETag": '"old"', "Metadata": {"rpr-sha256": "DIFFERENT"}},
            expected_params={"Bucket": "b", "Key": "p/a.json"},
        )
        new_payload = {"z": 9}
        stub.add_response(
            "put_object",
            service_response={"ETag": '"new"'},
            expected_params={
                "Bucket": "b",
                "Key": "p/a.json",
                "Body": _json_body(new_payload),
                "Metadata": ANY,
            },
        )
        backend.save("a", {"id": "a", **new_payload}, "")


def test_list_handles_multiple_s3_pages_and_paginates_locally():
    client = boto3.client("s3", region_name="us-east-1")
    backend = S3Backend(bucket="b", prefix="x", client=client)
    with Stubber(client) as stub:
        stub.add_response(
            "list_objects_v2",
            service_response={
                "IsTruncated": True,
                "NextContinuationToken": "t1",
                "KeyCount": 2,
                "Contents": [
                    {"Key": "x/y/b.json"},
                    {"Key": "x/y/a.json"},
                ],
            },
            expected_params={"Bucket": "b", "Prefix": "x/y/"},
        )
        stub.add_response(
            "list_objects_v2",
            service_response={
                "IsTruncated": False,
                "KeyCount": 1,
                "Contents": [
                    {"Key": "x/y/c.json"},
                ],
            },
            expected_params={"Bucket": "b", "Prefix": "x/y/", "ContinuationToken": "t1"},
        )
        stub.add_response(
            "get_object",
            service_response={
                "Body": botocore.response.StreamingBody(raw_stream=io.BytesIO(_json_body({"v": 3})), content_length=7),
                "ETag": '"e3"',
            },
            expected_params={"Bucket": "b", "Key": "x/y/c.json"},
        )
        items, total = backend.list("y", page=2, per_page=2)
        assert total == 3
        assert [i["id"] for i in items] == ["c"]


def test_list_empty_prefix_returns_zero():
    client = boto3.client("s3", region_name="us-east-1")
    backend = S3Backend(bucket="b", prefix="p", client=client)
    with Stubber(client) as stub:
        stub.add_response(
            "list_objects_v2",
            service_response={"IsTruncated": False, "KeyCount": 0, "Contents": []},
            expected_params={"Bucket": "b", "Prefix": "p/z/"},
        )
        items, total = backend.list("z")
        assert items == [] and total == 0


def test_list_deterministic_order_across_calls():
    client = boto3.client("s3", region_name="us-east-1")
    backend = S3Backend(bucket="b", prefix="x", client=client)
    with Stubber(client) as stub:
        stub.add_response(
            "list_objects_v2",
            service_response={
                "IsTruncated": False,
                "KeyCount": 3,
                "Contents": [
                    {"Key": "x/y/b.json"},
                    {"Key": "x/y/c.json"},
                    {"Key": "x/y/a.json"},
                ],
            },
            expected_params={"Bucket": "b", "Prefix": "x/y/"},
        )
        for key, val in [("a", 1), ("b", 2), ("c", 3)]:
            stub.add_response(
                "get_object",
                service_response={
                    "Body": botocore.response.StreamingBody(
                        raw_stream=io.BytesIO(_json_body({"v": val})), content_length=7
                    ),
                    "ETag": '"e"',
                },
                expected_params={"Bucket": "b", "Key": f"x/y/{key}.json"},
            )

        first, _ = backend.list("y", page=1, per_page=10)

        stub.add_response(
            "list_objects_v2",
            service_response={
                "IsTruncated": False,
                "KeyCount": 3,
                "Contents": [
                    {"Key": "x/y/c.json"},
                    {"Key": "x/y/a.json"},
                    {"Key": "x/y/b.json"},
                ],
            },
            expected_params={"Bucket": "b", "Prefix": "x/y/"},
        )
        for key, val in [("a", 1), ("b", 2), ("c", 3)]:
            stub.add_response(
                "get_object",
                service_response={
                    "Body": botocore.response.StreamingBody(
                        raw_stream=io.BytesIO(_json_body({"v": val})), content_length=7
                    ),
                    "ETag": '"e"',
                },
                expected_params={"Bucket": "b", "Key": f"x/y/{key}.json"},
            )

        second, _ = backend.list("y", page=1, per_page=10)
        assert [i["id"] for i in first] == ["a", "b", "c"]
        assert [i["id"] for i in second] == ["a", "b", "c"]
