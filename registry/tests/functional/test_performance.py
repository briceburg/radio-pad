import logging
import time
from pathlib import Path

import boto3
import pytest

from datastore import DataStore
from datastore.backends import S3Backend
from models.account import Account
from models.station_preset import GlobalStationPreset

NUM_ACCOUNTS = 5000
NUM_PRESETS = 1000


@pytest.mark.performance
def test_pagination_performance(functional_tests_root: Path):
    """
    Tests the pagination performance with a large number of records.
    """
    data_path = functional_tests_root / "perf_data"
    datastore = DataStore(data_path=str(data_path))

    # Seed a large number of accounts
    for i in range(NUM_ACCOUNTS):
        account_id = f"test-account-{i}"
        account = Account(id=account_id, name=f"Test Account {i}")
        datastore.accounts.save(account)

    # Seed a large number of global presets
    for i in range(NUM_PRESETS):
        preset_id = f"global-preset-{i}"
        preset = GlobalStationPreset(
            id=preset_id,
            name=f"Global Preset {i}",
            stations=[
                {
                    "name": f"Station {i}",
                    "url": f"http://example.com/stream-{i}",
                }
            ],
        )
        datastore.global_presets.save(preset)

    # Test fetching the first page of accounts
    paged_accounts = datastore.accounts.list(page=1, per_page=100)
    assert len(paged_accounts) == 100

    # Test fetching the first page of global presets
    paged_presets = datastore.global_presets.list(page=1, per_page=100)
    assert len(paged_presets) == 100


@pytest.fixture
def s3_backend():
    pytest.importorskip("moto")
    from moto import mock_aws

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        yield S3Backend(bucket="test-bucket", prefix="test-prefix")


@pytest.mark.performance
@pytest.mark.parametrize(
    "page_to_fetch, per_page",
    [
        (2, 100),
        (45, 100),
    ],
)
def test_s3_pagination_performance(s3_backend: S3Backend, page_to_fetch: int, per_page: int):
    """
    Tests the pagination performance of the S3 backend with a large number of records.
    """
    # Seed a large number of objects
    for i in range(NUM_ACCOUNTS):
        s3_backend.save(f"object-{i}", {"data": f"value-{i}"}, "test-path")

    # Time the pagination
    start_time = time.perf_counter()
    result = s3_backend.list("test-path", page=page_to_fetch, per_page=per_page)
    end_time = time.perf_counter()

    duration = end_time - start_time
    logging.info(
        f"\nS3 pagination for page {page_to_fetch} ({per_page} items/page) "
        f"with {NUM_ACCOUNTS} objects took {duration:.4f} seconds."
    )
    assert len(result) == per_page
