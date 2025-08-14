from __future__ import annotations

import io
import json
from typing import Any

import boto3
import botocore
from botocore.stub import Stubber, ANY

from datastore.backends.s3_store import S3FileStore


def _json_body(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")


def test_get_nonexistent_returns_none():
    client = boto3.client("s3", region_name="us-east-1")
    store = S3FileStore(bucket="b", prefix="p", client=client)
    with Stubber(client) as stub:
        stub.add_client_error(
            "get_object",
            service_error_code="NoSuchKey",
            service_message="not found",
            http_status_code=404,
            expected_params={"Bucket": "b", "Key": "p/a.json"},
        )
        data, token = store.get("a", "")
        assert data is None and token is None


def test_save_new_then_get_roundtrip():
    client = boto3.client("s3", region_name="us-east-1")
    store = S3FileStore(bucket="b", prefix="p", client=client)
    with Stubber(client) as stub:
        # save: HEAD 404 then PUT with body and metadata
        stub.add_client_error(
            "head_object",
            service_error_code="404",
            service_message="not found",
            http_status_code=404,
            expected_params={"Bucket": "b", "Key": "p/a.json"},
        )
        expected_payload = {"x": 1}
        # we can't predict hash here; accept any metadata but ensure key/bucket/body provided
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
        store.save("a", {"id": "a", **expected_payload}, "")

        # get: return body and VersionId token
        stub.add_response(
            "get_object",
            service_response={
                "Body": botocore.response.StreamingBody(raw_stream=io.BytesIO(_json_body(expected_payload)), content_length=len(_json_body(expected_payload))),
                "ETag": '"etag"',
                "VersionId": "v1",
            },
            expected_params={"Bucket": "b", "Key": "p/a.json"},
        )
        val, token = store.get("a", "")
        assert val == expected_payload
        assert token == "v1"


def test_save_noop_when_content_hash_matches():
    from datastore.core.helpers import compute_etag

    client = boto3.client("s3", region_name="us-east-1")
    store = S3FileStore(bucket="b", prefix="p", client=client)
    payload = {"x": 1}

    # Compute expected content hash used by the backend
    expected_hash = compute_etag(payload)

    with Stubber(client) as stub:
        # Existing object with matching content hash: save should be a no-op (no PUT)
        stub.add_response(
            "head_object",
            service_response={
                "ETag": '"e1"',
                "Metadata": {"rpr-sha256": expected_hash},
            },
            expected_params={"Bucket": "b", "Key": "p/a.json"},
        )
        # If code erroneously performs a PUT, Stubber will raise since no put_object response is registered.
        store.save("a", payload, "")


def test_save_if_match_mismatch_raises():
    client = boto3.client("s3", region_name="us-east-1")
    store = S3FileStore(bucket="b", prefix="p", client=client)
    with Stubber(client) as stub:
        stub.add_response(
            "head_object",
            service_response={"ETag": '"e1"', "VersionId": "v1", "Metadata": {}},
            expected_params={"Bucket": "b", "Key": "p/a.json"},
        )
        try:
            store.save("a", {"x": 2}, "", if_match="v2")
            assert False, "expected ValueError"
        except ValueError:
            pass


def test_list_returns_items_and_total():
    client = boto3.client("s3", region_name="us-east-1")
    store = S3FileStore(bucket="b", prefix="x", client=client)
    with Stubber(client) as stub:
        # list (single page)
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
        # get first page items (2)
        stub.add_response(
            "get_object",
            service_response={"Body": botocore.response.StreamingBody(raw_stream=io.BytesIO(_json_body({"v": 1})), content_length=7), "ETag": '"e1"'},
            expected_params={"Bucket": "b", "Key": "x/y/a.json"},
        )
        stub.add_response(
            "get_object",
            service_response={"Body": botocore.response.StreamingBody(raw_stream=io.BytesIO(_json_body({"v": 2})), content_length=7), "ETag": '"e2"'},
            expected_params={"Bucket": "b", "Key": "x/y/b.json"},
        )
        items, total = store.list("y", page=1, per_page=2)
        assert total == 3
        assert len(items) == 2
        assert items[0]["id"] == "a" and items[0]["v"] == 1
        assert items[1]["id"] == "b" and items[1]["v"] == 2


def test_delete_success_and_not_found():
    client = boto3.client("s3", region_name="us-east-1")
    store = S3FileStore(bucket="b", prefix="p", client=client)
    with Stubber(client) as stub:
        stub.add_response("delete_object", service_response={}, expected_params={"Bucket": "b", "Key": "p/a.json"})
        assert store.delete("a", "") is True
        stub.add_client_error("delete_object", service_error_code="404", service_message="nf", http_status_code=404, expected_params={"Bucket": "b", "Key": "p/b.json"})
        assert store.delete("b", "") is False


def test_get_uses_etag_when_version_missing():
    client = boto3.client("s3", region_name="us-east-1")
    store = S3FileStore(bucket="b", prefix="p", client=client)
    with Stubber(client) as stub:
        payload = {"y": 7}
        stub.add_response(
            "get_object",
            service_response={
                "Body": botocore.response.StreamingBody(raw_stream=io.BytesIO(_json_body(payload)), content_length=len(_json_body(payload))),
                "ETag": '"abc123"',
            },
            expected_params={"Bucket": "b", "Key": "p/a.json"},
        )
        data, token = store.get("a", "")
        assert data == payload
        # ETag should be unquoted
        assert token == "abc123"


def test_save_if_match_success_puts():
    client = boto3.client("s3", region_name="us-east-1")
    store = S3FileStore(bucket="b", prefix="p", client=client)
    with Stubber(client) as stub:
        # Existing object reports VersionId=v1
        stub.add_response(
            "head_object",
            service_response={"VersionId": "v1", "ETag": '"e1"', "Metadata": {}},
            expected_params={"Bucket": "b", "Key": "p/a.json"},
        )
        # if_match matches, so we expect a PUT
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
        store.save("a", {"id": "a", **expected_payload}, "", if_match="v1")


def test_save_changed_content_triggers_put():
    client = boto3.client("s3", region_name="us-east-1")
    store = S3FileStore(bucket="b", prefix="p", client=client)
    with Stubber(client) as stub:
        # Existing content hash differs from new hash; should PUT
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
        store.save("a", {"id": "a", **new_payload}, "")


def test_list_handles_multiple_s3_pages_and_paginates_locally():
    client = boto3.client("s3", region_name="us-east-1")
    store = S3FileStore(bucket="b", prefix="x", client=client)
    with Stubber(client) as stub:
        # First S3 page truncated with a,b then continuation
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
        # Second S3 page with c
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
        # Only page 2 of our logical list will fetch 'c'
        stub.add_response(
            "get_object",
            service_response={
                "Body": botocore.response.StreamingBody(raw_stream=io.BytesIO(_json_body({"v": 3})), content_length=7),
                "ETag": '"e3"',
            },
            expected_params={"Bucket": "b", "Key": "x/y/c.json"},
        )
        items, total = store.list("y", page=2, per_page=2)
        # Keys are sorted lexicographically: a,b,c -> total 3, page2 yields [c]
        assert total == 3
        assert [i["id"] for i in items] == ["c"]


def test_list_empty_prefix_returns_zero():
    client = boto3.client("s3", region_name="us-east-1")
    store = S3FileStore(bucket="b", prefix="p", client=client)
    with Stubber(client) as stub:
        stub.add_response(
            "list_objects_v2",
            service_response={"IsTruncated": False, "KeyCount": 0, "Contents": []},
            expected_params={"Bucket": "b", "Prefix": "p/z/"},
        )
        items, total = store.list("z")
        assert items == [] and total == 0


def test_list_deterministic_order_across_calls():
    client = boto3.client("s3", region_name="us-east-1")
    store = S3FileStore(bucket="b", prefix="x", client=client)
    with Stubber(client) as stub:
        # First list call returns unsorted keys
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
        # get a,b,c in sorted order
        for key, val in [("a", 1), ("b", 2), ("c", 3)]:
            stub.add_response(
                "get_object",
                service_response={
                    "Body": botocore.response.StreamingBody(raw_stream=io.BytesIO(_json_body({"v": val})), content_length=7),
                    "ETag": '"e"',
                },
                expected_params={"Bucket": "b", "Key": f"x/y/{key}.json"},
            )

        first, _ = store.list("y", page=1, per_page=10)

        # Second list call with same unsorted keys
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
                    "Body": botocore.response.StreamingBody(raw_stream=io.BytesIO(_json_body({"v": val})), content_length=7),
                    "ETag": '"e"',
                },
                expected_params={"Bucket": "b", "Key": f"x/y/{key}.json"},
            )

        second, _ = store.list("y", page=1, per_page=10)
        assert [i["id"] for i in first] == ["a", "b", "c"]
        assert [i["id"] for i in second] == ["a", "b", "c"]
