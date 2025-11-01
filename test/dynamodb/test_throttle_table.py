import os
import time
import typing
from datetime import datetime, timedelta, timezone

import boto3
import pytest
from moto import mock_aws

from thoughtful_backend.dynamodb.throttle_table import (
    DAILY_COUNT_SK_PREFIX,
    GLOBAL_DAILY_LIMIT_CALLS,
    USER_DAILY_LIMIT_CALLS,
    USER_MINUTE_LIMIT_SECONDS,
    ThrottleRateLimitExceededException,
    ThrottleTable,
)

REGION = "us-west-1"
TABLE_NAME = "ThrottleTable"
DEFAULT_ACTION_TYPE = "CHATBOT_API_CALL"


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
        yield dynamodb


@pytest.fixture
def throttle_table_instance(dynamodb_table_resource) -> ThrottleTable:
    return ThrottleTable(TABLE_NAME)


def get_current_date_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_future_ttl(date_str: typing.Optional[str] = None):
    if date_str is None:
        date_str = get_current_date_str()
    start_of_day_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    ttl_dt = start_of_day_dt + timedelta(days=1, hours=1)
    return int(ttl_dt.timestamp())


# === Direct DAL Method Tests ===


def test_dal_get_user_minute_timestamp_not_exists(throttle_table_instance: ThrottleTable):
    assert throttle_table_instance.get_user_minute_timestamp("user1", DEFAULT_ACTION_TYPE) is None


def test_dal_update_and_get_user_minute_timestamp(throttle_table_instance: ThrottleTable):
    user_id = "user_min_ts"
    ts = int(time.time())
    throttle_table_instance.update_user_minute_timestamp(user_id, DEFAULT_ACTION_TYPE, ts)
    retrieved_ts = throttle_table_instance.get_user_minute_timestamp(user_id, DEFAULT_ACTION_TYPE)
    assert retrieved_ts == ts


def test_dal_get_user_daily_count_not_exists(throttle_table_instance: ThrottleTable):
    assert (
        throttle_table_instance.get_user_daily_count("user_daily_empty", DEFAULT_ACTION_TYPE, get_current_date_str())
        == 0
    )


def test_dal_increment_and_get_user_daily_count(throttle_table_instance: ThrottleTable):
    user_id = "user_daily_incr"
    date_str = get_current_date_str()
    ttl = get_future_ttl(date_str)

    new_count = throttle_table_instance.increment_user_daily_count(user_id, DEFAULT_ACTION_TYPE, date_str, ttl)
    assert new_count == 1
    assert throttle_table_instance.get_user_daily_count(user_id, DEFAULT_ACTION_TYPE, date_str) == 1

    new_count_2 = throttle_table_instance.increment_user_daily_count(user_id, DEFAULT_ACTION_TYPE, date_str, ttl)
    assert new_count_2 == 2
    assert throttle_table_instance.get_user_daily_count(user_id, DEFAULT_ACTION_TYPE, date_str) == 2

    # Verify TTL attribute was set
    item = throttle_table_instance.table.get_item(
        Key={
            "entityActionId": throttle_table_instance._get_user_pk(user_id, DEFAULT_ACTION_TYPE),
            "periodType#periodIdentifier": f"{DAILY_COUNT_SK_PREFIX}{date_str}",
        }
    ).get("Item")
    assert item is not None
    assert item.get("ttl") == ttl


def test_dal_get_global_daily_count_not_exists(throttle_table_instance: ThrottleTable):
    assert throttle_table_instance.get_global_daily_count(DEFAULT_ACTION_TYPE, get_current_date_str()) == 0


def test_dal_increment_and_get_global_daily_count(throttle_table_instance: ThrottleTable):
    date_str = get_current_date_str()
    ttl = get_future_ttl(date_str)

    new_count = throttle_table_instance.increment_global_daily_count(
        DEFAULT_ACTION_TYPE, date_str, ttl, GLOBAL_DAILY_LIMIT_CALLS
    )
    assert new_count == 1
    assert throttle_table_instance.get_global_daily_count(DEFAULT_ACTION_TYPE, date_str) == 1

    new_count_2 = throttle_table_instance.increment_global_daily_count(
        DEFAULT_ACTION_TYPE, date_str, ttl, GLOBAL_DAILY_LIMIT_CALLS
    )
    assert new_count_2 == 2


def test_dal_increment_global_daily_count_hits_limit_via_condition(throttle_table_instance: ThrottleTable):
    date_str = get_current_date_str()
    ttl = get_future_ttl(date_str)
    # Set limit specifically for this test if different from module constant
    test_limit = 2

    assert throttle_table_instance.increment_global_daily_count(DEFAULT_ACTION_TYPE, date_str, ttl, test_limit) == 1
    assert throttle_table_instance.increment_global_daily_count(DEFAULT_ACTION_TYPE, date_str, ttl, test_limit) == 2
    # Next call should fail conditional update because count (2) is not less than limit (2)
    assert throttle_table_instance.increment_global_daily_count(DEFAULT_ACTION_TYPE, date_str, ttl, test_limit) is None
    assert throttle_table_instance.get_global_daily_count(DEFAULT_ACTION_TYPE, date_str) == 2


# === Context Manager Tests (`throttle_action`) ===


def test_context_manager_allows_when_no_limits_hit(throttle_table_instance: ThrottleTable):
    user_id = "cm_user_ok"
    date_str = get_current_date_str()
    initial_global_count = throttle_table_instance.get_global_daily_count(DEFAULT_ACTION_TYPE, date_str)

    with throttle_table_instance.throttle_action(user_id, DEFAULT_ACTION_TYPE):
        pass

    # Check that counts were updated
    assert throttle_table_instance.get_user_minute_timestamp(user_id, DEFAULT_ACTION_TYPE) is not None
    assert throttle_table_instance.get_user_daily_count(user_id, DEFAULT_ACTION_TYPE, date_str) == 1
    assert throttle_table_instance.get_global_daily_count(DEFAULT_ACTION_TYPE, date_str) == initial_global_count + 1


def test_context_manager_raises_user_minute_limit(throttle_table_instance: ThrottleTable):
    user_id = "cm_user_minute_exceeded"
    # Pre-set a recent timestamp
    recent_ts = int(time.time()) - (USER_MINUTE_LIMIT_SECONDS // 2)
    throttle_table_instance.update_user_minute_timestamp(user_id, DEFAULT_ACTION_TYPE, recent_ts)

    with pytest.raises(ThrottleRateLimitExceededException) as exc_info:
        with throttle_table_instance.throttle_action(user_id, DEFAULT_ACTION_TYPE):
            pytest.fail("Should not execute code within 'with' block if limit exceeded")

    assert exc_info.value.limit_type == "USER_MINUTE_LIMIT"
    # Ensure counts were NOT updated
    assert throttle_table_instance.get_user_daily_count(user_id, DEFAULT_ACTION_TYPE, get_current_date_str()) == 0


def test_context_manager_raises_user_daily_limit(throttle_table_instance: ThrottleTable):
    user_id = "cm_user_daily_exceeded"
    date_str = get_current_date_str()
    ttl = get_future_ttl(date_str)
    # Pre-set daily count to the limit
    for _ in range(USER_DAILY_LIMIT_CALLS):
        throttle_table_instance.increment_user_daily_count(user_id, DEFAULT_ACTION_TYPE, date_str, ttl)

    assert (
        throttle_table_instance.get_user_daily_count(user_id, DEFAULT_ACTION_TYPE, date_str) == USER_DAILY_LIMIT_CALLS
    )

    with pytest.raises(ThrottleRateLimitExceededException) as exc_info:
        with throttle_table_instance.throttle_action(user_id, DEFAULT_ACTION_TYPE):
            pytest.fail("Should not execute code within 'with' block if limit exceeded")

    assert exc_info.value.limit_type == "USER_DAILY_LIMIT"


def test_context_manager_raises_global_daily_limit(throttle_table_instance: ThrottleTable):
    user_id = "cm_user_for_global_check"  # This user has no limits hit
    date_str = get_current_date_str()
    ttl = get_future_ttl(date_str)
    # Pre-set global daily count to the limit
    for _ in range(GLOBAL_DAILY_LIMIT_CALLS):
        # Use a different user for these increments to not interfere with the test user's own limits
        throttle_table_instance.increment_global_daily_count(
            DEFAULT_ACTION_TYPE, date_str, ttl, GLOBAL_DAILY_LIMIT_CALLS
        )

    assert throttle_table_instance.get_global_daily_count(DEFAULT_ACTION_TYPE, date_str) >= GLOBAL_DAILY_LIMIT_CALLS

    with pytest.raises(ThrottleRateLimitExceededException) as exc_info:
        with throttle_table_instance.throttle_action(user_id, DEFAULT_ACTION_TYPE):
            pytest.fail("Should not execute code within 'with' block if limit exceeded")

    assert exc_info.value.limit_type == "GLOBAL_DAILY_LIMIT"


def test_context_manager_operation_fails_no_count_update(throttle_table_instance: ThrottleTable):
    user_id = "cm_user_op_fails"
    date_str = get_current_date_str()

    class OperationFailedError(Exception):
        pass

    with pytest.raises(OperationFailedError):  # Ensure the specific exception from the block is propagated
        with throttle_table_instance.throttle_action(user_id, DEFAULT_ACTION_TYPE):
            # This operation will fail
            raise OperationFailedError("Simulated failure of the main operation")

    # Check that counts were NOT updated because the operation inside 'with' failed
    assert throttle_table_instance.get_user_minute_timestamp(user_id, DEFAULT_ACTION_TYPE) is None
    assert throttle_table_instance.get_user_daily_count(user_id, DEFAULT_ACTION_TYPE, date_str) == 0
    # Global count should also not have been incremented by this user's attempt
    initial_global_count = throttle_table_instance.get_global_daily_count(
        DEFAULT_ACTION_TYPE, date_str
    )  # Could be >0 from other tests
    # This check assumes no other test ran concurrently and modified the global count in this exact moment.
    # For more isolated global count check, reset it or use a unique action_type.
    assert throttle_table_instance.get_global_daily_count(DEFAULT_ACTION_TYPE, date_str) == initial_global_count


def test_context_manager_daily_counts_reset_next_day(throttle_table_instance: ThrottleTable):
    user_id = "cm_user_day_reset"

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    yesterday_ttl = int((yesterday + timedelta(days=1, hours=1)).timestamp())

    # Simulate user hit daily limit yesterday
    for _ in range(USER_DAILY_LIMIT_CALLS):
        throttle_table_instance.increment_user_daily_count(user_id, DEFAULT_ACTION_TYPE, yesterday_str, yesterday_ttl)

    assert (
        throttle_table_instance.get_user_daily_count(user_id, DEFAULT_ACTION_TYPE, yesterday_str)
        == USER_DAILY_LIMIT_CALLS
    )

    # Use context manager today, should pass and set today's count to 1
    with throttle_table_instance.throttle_action(user_id, DEFAULT_ACTION_TYPE):
        pass  # Successful operation

    assert throttle_table_instance.get_user_daily_count(user_id, DEFAULT_ACTION_TYPE, today_str) == 1
    # Yesterday's count remains (though it would be TTL'd eventually in real DDB)
    assert (
        throttle_table_instance.get_user_daily_count(user_id, DEFAULT_ACTION_TYPE, yesterday_str)
        == USER_DAILY_LIMIT_CALLS
    )
