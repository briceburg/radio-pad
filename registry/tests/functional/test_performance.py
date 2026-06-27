import logging
import time
from collections.abc import Generator
from pathlib import Path

import boto3
import pytest

from datastore import DataStore
from datastore.backends import LocalBackend, S3Backend
from models import AccountSpec, RadioDialSpec

NUM_ACCOUNTS = 5000
NUM_RADIO_DIALS = 1000


@pytest.mark.performance
def test_pagination_performance(tmp_path: Path) -> None:
    """
    Tests the pagination performance with a large number of records.
    """
    data_path = tmp_path / "perf_data"
    datastore = DataStore(backend=LocalBackend(base_path=str(data_path)))

    # Seed a large number of accounts
    for i in range(NUM_ACCOUNTS):
        account_id = f"test-account-{i}"
        datastore.accounts.upsert(account_id, AccountSpec(name=f"Test Account {i}"))

    # Seed a large number of account-scoped RadioDials.
    for i in range(NUM_RADIO_DIALS):
        datastore.radio_dials.upsert(
            f"radio-dial-{i}",
            RadioDialSpec(name=f"RadioDial {i}", stations=[]),
            path_params={"account_id": "performance"},
        )

    start_time = time.perf_counter()
    paged_accounts = datastore.accounts.list(page=1, per_page=100)
    paged_radio_dials = datastore.radio_dials.list(path_params={"account_id": "performance"}, page=1, per_page=100)
    duration = time.perf_counter() - start_time

    logging.info(
        "\nLocal pagination for 100-item first pages with %s accounts and %s RadioDials took %.4f seconds.",
        NUM_ACCOUNTS,
        NUM_RADIO_DIALS,
        duration,
    )

    assert len(paged_accounts) == 100
    assert len(paged_radio_dials) == 100


@pytest.fixture
def s3_backend() -> Generator[S3Backend]:
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
def test_s3_pagination_performance(s3_backend: S3Backend, page_to_fetch: int, per_page: int) -> None:
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
