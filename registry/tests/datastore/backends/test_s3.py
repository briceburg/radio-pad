"""Tests for S3 backend list filtering to ensure nested objects are excluded."""

from __future__ import annotations

from collections.abc import Generator

import boto3
import pytest
from moto import mock_aws

from datastore.backends.s3 import S3Backend


@pytest.fixture
def s3_backend() -> Generator[S3Backend]:
    """Creates an S3Backend with mocked AWS for testing."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        bucket = "test-bucket"
        client.create_bucket(Bucket=bucket)
        backend = S3Backend(bucket=bucket, prefix="test", client=client)
        yield backend


class TestS3BackendListFiltering:
    """Test that S3Backend.list() properly filters out nested objects."""

    def test_list_excludes_nested_objects(self, s3_backend: S3Backend) -> None:
        """Test that listing accounts excludes nested player data."""
        # Setup: account with nested player data (reproduces the original issue)
        s3_backend.save("briceburg", {"name": "Briceburg"}, "accounts")
        s3_backend.save("living-room", {"name": "Living Room"}, "accounts", "briceburg", "players")

        # Should only return direct accounts, not nested players
        result = s3_backend.list("accounts")
        assert len(result) == 1
        assert result[0]["id"] == "briceburg"
        assert "living-room" not in [item["id"] for item in result]

    def test_list_with_multiple_nesting_levels(self, s3_backend: S3Backend) -> None:
        """Test proper filtering with complex nested structures."""
        # Setup accounts and deeply nested objects
        s3_backend.save("account1", {"name": "Account 1"}, "accounts")
        s3_backend.save("account2", {"name": "Account 2"}, "accounts")
        s3_backend.save("player1", {"name": "Player 1"}, "accounts", "account1", "players")
        s3_backend.save("deep-object", {"name": "Deep"}, "accounts", "account1", "players", "nested")

        # Accounts list should only include direct accounts
        accounts = s3_backend.list("accounts")
        account_ids = sorted([item["id"] for item in accounts])
        assert account_ids == ["account1", "account2"]

        # Players list should only include direct players
        players = s3_backend.list("accounts", "account1", "players")
        assert len(players) == 1
        assert players[0]["id"] == "player1"

    def test_list_empty_and_nested_only_paths(self, s3_backend: S3Backend) -> None:
        """Test edge cases: empty paths and paths with only nested objects."""
        # Empty path
        assert s3_backend.list("empty") == []

        # Path with only nested objects (no direct children)
        s3_backend.save("nested", {"name": "Nested"}, "path", "deep", "nested")
        assert s3_backend.list("path") == []
