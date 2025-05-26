# test/dynamodb/test_throttling_store_table.py
import os
import time
import typing
from datetime import datetime, timedelta, timezone

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from aws_src_sample.dynamodb.throttling_store_table import (
    DAILY_COUNT_PREFIX,
    MINUTE_TRACK_PREFIX,
    ThrottlingStoreTable,
)

REGION = "us-east-2"
TABLE_NAME = "test-throttling-store"
ACTION_TYPE_TEST = "TEST_ACTION"


@pytest.fixture(scope="function")
def aws_credentials() -> typing.Iterator:
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = REGION
    yield
    del os.environ["AWS_ACCESS_KEY_ID"]
    del os.environ["AWS_SECRET_ACCESS_KEY"]
    del os.environ["AWS_SECURITY_TOKEN"]
    del os.environ["AWS_SESSION_TOKEN"]
    del os.environ["AWS_DEFAULT_REGION"]


@pytest.fixture
def dynamodb_table_resource(aws_credentials):
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "entityActionId", "KeyType": "HASH"},
                {"AttributeName": "periodType#periodIdentifier", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "entityActionId", "AttributeType": "S"},
                {"AttributeName": "periodType#periodIdentifier", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield dynamodb  # Yield the resource, not the table object directly


@pytest.fixture
def throttling_table_instance(dynamodb_table_resource) -> ThrottlingStoreTable:
    return ThrottlingStoreTable(TABLE_NAME)


def get_test_date_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_test_ttl():
    return int((datetime.now(timezone.utc) + timedelta(days=1, hours=1)).timestamp())


def test_get_user_minute_timestamp_not_exists(throttling_table_instance: ThrottlingStoreTable):
    assert throttling_table_instance.get_user_minute_timestamp("user1", ACTION_TYPE_TEST) is None


def test_update_and_get_user_minute_timestamp(throttling_table_instance: ThrottlingStoreTable):
    user_id = "user2"
    ts = int(time.time())
    throttling_table_instance.update_user_minute_timestamp(user_id, ACTION_TYPE_TEST, ts)
    retrieved_ts = throttling_table_instance.get_user_minute_timestamp(user_id, ACTION_TYPE_TEST)
    assert retrieved_ts == ts


def test_get_user_daily_count_not_exists(throttling_table_instance: ThrottlingStoreTable):
    assert throttling_table_instance.get_user_daily_count("user3", ACTION_TYPE_TEST, get_test_date_str()) == 0


def test_increment_and_get_user_daily_count(throttling_table_instance: ThrottlingStoreTable):
    user_id = "user4"
    date_str = get_test_date_str()
    ttl = get_test_ttl()

    new_count = throttling_table_instance.increment_user_daily_count(user_id, ACTION_TYPE_TEST, date_str, ttl)
    assert new_count == 1
    assert throttling_table_instance.get_user_daily_count(user_id, ACTION_TYPE_TEST, date_str) == 1

    new_count_2 = throttling_table_instance.increment_user_daily_count(user_id, ACTION_TYPE_TEST, date_str, ttl)
    assert new_count_2 == 2
    assert throttling_table_instance.get_user_daily_count(user_id, ACTION_TYPE_TEST, date_str) == 2

    # Verify TTL was set (moto might not fully simulate TTL deletion, but we check for attribute presence)
    pk = f"USER#{user_id}#{ACTION_TYPE_TEST}"
    sk = f"{DAILY_COUNT_PREFIX}{date_str}"
    item = throttling_table_instance.table.get_item(Key={"entityActionId": pk, "periodType#periodIdentifier": sk}).get(
        "Item"
    )
    assert item is not None
    assert item.get("ttl") == ttl


def test_get_global_daily_count_not_exists(throttling_table_instance: ThrottlingStoreTable):
    assert throttling_table_instance.get_global_daily_count(ACTION_TYPE_TEST, get_test_date_str()) == 0


def test_increment_and_get_global_daily_count(throttling_table_instance: ThrottlingStoreTable):
    date_str = get_test_date_str()
    ttl = get_test_ttl()
    limit = 5

    new_count = throttling_table_instance.increment_global_daily_count(ACTION_TYPE_TEST, date_str, ttl, limit)
    assert new_count == 1
    assert throttling_table_instance.get_global_daily_count(ACTION_TYPE_TEST, date_str) == 1

    new_count_2 = throttling_table_instance.increment_global_daily_count(ACTION_TYPE_TEST, date_str, ttl, limit)
    assert new_count_2 == 2


def test_increment_global_daily_count_hits_limit(throttling_table_instance: ThrottlingStoreTable):
    date_str = get_test_date_str()
    ttl = get_test_ttl()
    limit = 2

    assert throttling_table_instance.increment_global_daily_count(ACTION_TYPE_TEST, date_str, ttl, limit) == 1
    assert throttling_table_instance.increment_global_daily_count(ACTION_TYPE_TEST, date_str, ttl, limit) == 2
    # Next call should fail conditional update because count (2) is not less than limit (2)
    assert throttling_table_instance.increment_global_daily_count(ACTION_TYPE_TEST, date_str, ttl, limit) is None
    assert (
        throttling_table_instance.get_global_daily_count(ACTION_TYPE_TEST, date_str) == 2
    )  # Count should remain at the limit


def test_increment_global_daily_count_attribute_not_exists_then_hits_limit(
    throttling_table_instance: ThrottlingStoreTable,
):
    date_str = get_test_date_str()
    ttl = get_test_ttl()
    limit = 1  # Limit is 1, first increment makes it 1 (which is not < 1 for next call)

    assert throttling_table_instance.increment_global_daily_count(ACTION_TYPE_TEST, date_str, ttl, limit) == 1
    assert throttling_table_instance.get_global_daily_count(ACTION_TYPE_TEST, date_str) == 1
    # Next call should fail conditional update
    assert throttling_table_instance.increment_global_daily_count(ACTION_TYPE_TEST, date_str, ttl, limit) is None
    assert throttling_table_instance.get_global_daily_count(ACTION_TYPE_TEST, date_str) == 1
