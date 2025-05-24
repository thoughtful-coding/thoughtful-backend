import os
import typing

import boto3
import pytest
from moto import mock_aws

from aws_src_sample.dynamodb.user_progress_table import (
    SectionCompletionModel,
    UserProgressTable,
)

REGION = "us-east-2"
TABLE_NAME = "test-user-progress-table"


@pytest.fixture(scope="function")
def aws_credentials() -> typing.Iterator:
    """
    Mocked AWS Credentials for moto.
    """
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
def dynamodb_table_object(aws_credentials) -> typing.Iterator:
    """Creates the mock DynamoDB table using moto's context (via class decorator)."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=REGION)

        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "userId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "userId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield table


@pytest.fixture
def user_progress_table_instance(dynamodb_table_object) -> UserProgressTable:
    """Create UserProgressTable instance. Relies on @mock_aws on the class."""
    return UserProgressTable(TABLE_NAME)


@mock_aws
def test_table_init(user_progress_table_instance: UserProgressTable) -> None:
    """
    Test table initialization
    """
    assert user_progress_table_instance.table.table_name == TABLE_NAME


@mock_aws
def test_get_progress_user_not_found(user_progress_table_instance: UserProgressTable) -> None:
    """
    Test getting progress for non-existent user.
    """
    result = user_progress_table_instance.get_progress("non-existent-user")
    assert result is None


@mock_aws
def test_get_progress_user_exists(user_progress_table_instance: UserProgressTable, dynamodb_table_object) -> None:
    """
    Test getting progress for existing user.
    """
    user_id = "test-user-123"
    test_data = {
        "userId": user_id,
        "completion": {"l1": {"s1": "5", "s2": "10"}},
    }

    # Put item using the moto-managed table object directly for setup
    # or use a method on user_progress_table_instance if it has a put_item method
    dynamodb_table_object = dynamodb_table_object  # This is the table object from the fixture
    dynamodb_table_object.put_item(Item=test_data)

    # Alternatively, if your UserProgressTable has its own put method that uses self.table:
    # user_progress_table_instance.put_raw_item(test_data) # Assuming such a method exists

    # Test retrieval
    result = user_progress_table_instance.get_progress(user_id)
    assert result is not None
    assert result.userId == user_id
    assert "l1" in result.completion
    assert result.completion["l1"] == {"s1": "5", "s2": "10"}


@mock_aws
def test_update_progress_empty(user_progress_table_instance: UserProgressTable, dynamodb_table_object) -> None:
    """
    Test updating progress with empty list.
    """
    user_id = "test-user-123"

    user_progress_table_instance.update_progress(user_id, [])
    result = user_progress_table_instance.get_progress(user_id)

    assert result is not None
    assert result.userId == user_id
    assert result.completion == {}


@mock_aws
def test_update_progress_single_update(user_progress_table_instance: UserProgressTable, dynamodb_table_object) -> None:
    """
    Test updating progress with single completion.
    """
    user_id = "test-user-123"

    user_progress_table_instance.update_progress(user_id, [SectionCompletionModel(lessonId="l1", sectionId="s1")])
    result = user_progress_table_instance.get_progress(user_id)

    assert result is not None
    assert result.userId == user_id
    assert "l1" in result.completion
    assert set(result.completion["l1"]) == {"s1"}


@mock_aws
def test_update_progress_triple_update(user_progress_table_instance: UserProgressTable, dynamodb_table_object) -> None:
    """
    Test updating progress multiple "updates"
    """
    user_id = "test-user-123"

    user_progress_table_instance.update_progress(user_id, [SectionCompletionModel(lessonId="l1", sectionId="s1")])
    user_progress_table_instance.update_progress(user_id, [SectionCompletionModel(lessonId="l1", sectionId="s2")])
    user_progress_table_instance.update_progress(user_id, [SectionCompletionModel(lessonId="l1", sectionId="s3")])
    result = user_progress_table_instance.get_progress(user_id)

    assert result is not None
    assert result.userId == user_id
    assert "l1" in result.completion
    assert set(result.completion["l1"]) == {"s1", "s2", "s3"}


@mock_aws
def test_update_progress_multi_lesson_updates(
    user_progress_table_instance: UserProgressTable, dynamodb_table_object
) -> None:
    user_id = "test-user-123"

    user_progress_table_instance.update_progress(user_id, [SectionCompletionModel(lessonId="l1", sectionId="s1")])
    user_progress_table_instance.update_progress(user_id, [SectionCompletionModel(lessonId="l1", sectionId="s2")])
    user_progress_table_instance.update_progress(user_id, [SectionCompletionModel(lessonId="l2", sectionId="s1")])
    result = user_progress_table_instance.get_progress(user_id)

    assert result is not None
    assert result.userId == user_id
    assert "l1" in result.completion
    assert set(result.completion["l1"]) == {"s1", "s2"}

    assert "l2" in result.completion
    assert set(result.completion["l2"]) == {"s1"}


@mock_aws
def test_update_progress_big_update(user_progress_table_instance: UserProgressTable, dynamodb_table_object) -> None:
    user_id = "test-user-123"

    user_progress_table_instance.update_progress(
        user_id,
        [
            SectionCompletionModel(lessonId="l1", sectionId="s1"),
            SectionCompletionModel(lessonId="l1", sectionId="s2"),
            SectionCompletionModel(lessonId="l2", sectionId="s1"),
        ],
    )
    result = user_progress_table_instance.get_progress(user_id)

    assert result is not None
    assert result.userId == user_id
    assert "l1" in result.completion
    assert set(result.completion["l1"]) == {"s1", "s2"}

    assert "l2" in result.completion
    assert set(result.completion["l2"]) == {"s1"}
