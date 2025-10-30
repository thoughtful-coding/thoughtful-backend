import os
import time

import boto3
import pytest
from moto import mock_aws

from thoughtful_backend.dynamodb.refresh_token_table import RefreshTokenTable
from thoughtful_backend.utils.base_types import UserId

REGION = "us-east-2"
TABLE_NAME = "test-refresh-token-table"


@pytest.fixture
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = REGION
    yield
    del os.environ["AWS_ACCESS_KEY_ID"]
    del os.environ["AWS_SECRET_ACCESS_KEY"]
    del os.environ["AWS_DEFAULT_REGION"]


@pytest.fixture
def dynamodb_table(aws_credentials):
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "userId", "KeyType": "HASH"},
                {"AttributeName": "tokenId", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "userId", "AttributeType": "S"},
                {"AttributeName": "tokenId", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


@pytest.fixture
def token_table(dynamodb_table) -> RefreshTokenTable:
    return RefreshTokenTable(TABLE_NAME)


def test_save_and_get_token(token_table: RefreshTokenTable):
    user_id = UserId("test-user-1")
    token_id = "test-token-123"
    ttl = int(time.time()) + 3600

    assert token_table.save_token(user_id, token_id, ttl) is True

    item = token_table.get_token(user_id, token_id)
    assert item is not None
    assert item["userId"] == user_id
    assert item["tokenId"] == token_id
    assert item["ttl"] == ttl


def test_get_non_existent_token(token_table: RefreshTokenTable):
    assert token_table.get_token(UserId("no-user"), "no-token") is None


def test_delete_token(token_table: RefreshTokenTable):
    user_id = UserId("user-to-delete")
    token_id = "token-to-delete"
    ttl = int(time.time()) + 3600

    token_table.save_token(user_id, token_id, ttl)
    assert token_table.get_token(user_id, token_id) is not None

    assert token_table.delete_token(user_id, token_id) is True
    assert token_table.get_token(user_id, token_id) is None
