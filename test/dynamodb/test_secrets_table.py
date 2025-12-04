import boto3
import pytest
from moto import mock_aws

from thoughtful_backend.dynamodb.secrets_table import SecretsTable

REGION = "us-west-1"
TABLE_NAME = "SecretsTable"


@pytest.fixture
def dynamodb_table(aws_credentials):
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "secretKey", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "secretKey", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


@pytest.fixture
def secrets_table(dynamodb_table) -> SecretsTable:
    # Clear cache before each test to avoid pollution
    SecretsTable._cache.clear()
    return SecretsTable(TABLE_NAME)


def test_get_jwt_secret_key_exists(secrets_table: SecretsTable):
    """Test retrieving an existing JWT secret."""
    # Manually insert JWT secret into the mock table
    secrets_table.table.put_item(
        Item={
            "secretKey": "JWT_SECRET",
            "secretValue": "test-jwt-secret-value-123",
            "description": "JWT secret for signing tokens",
            "updatedAt": "2025-01-01T00:00:00Z",
        }
    )

    secret_value = secrets_table.get_jwt_secret_key()
    assert secret_value == "test-jwt-secret-value-123"


def test_get_chatbot_api_key_exists(secrets_table: SecretsTable):
    """Test retrieving an existing ChatBot API key."""
    # Manually insert ChatBot API key into the mock table
    secrets_table.table.put_item(
        Item={
            "secretKey": "CHATBOT_API_KEY",
            "secretValue": "test-chatbot-api-key-456",
            "description": "ChatBot API key",
            "updatedAt": "2025-01-01T00:00:00Z",
        }
    )

    secret_value = secrets_table.get_chatbot_api_key()
    assert secret_value == "test-chatbot-api-key-456"


def test_get_jwt_secret_key_not_found(secrets_table: SecretsTable):
    """Test that KeyError is raised when JWT secret is not found."""
    with pytest.raises(KeyError) as exc_info:
        secrets_table.get_jwt_secret_key()
    assert "JWT_SECRET" in str(exc_info.value)


def test_get_chatbot_api_key_not_found(secrets_table: SecretsTable):
    """Test that KeyError is raised when ChatBot API key is not found."""
    with pytest.raises(KeyError) as exc_info:
        secrets_table.get_chatbot_api_key()
    assert "CHATBOT_API_KEY" in str(exc_info.value)


def test_secret_caching(secrets_table: SecretsTable):
    """Test that secrets are cached after first retrieval."""
    # Insert a secret
    secrets_table.table.put_item(
        Item={
            "secretKey": "JWT_SECRET",
            "secretValue": "cached-jwt-value",
            "description": "Cached JWT secret",
            "updatedAt": "2025-01-01T00:00:00Z",
        }
    )

    # First retrieval - should hit DynamoDB
    first_value = secrets_table.get_jwt_secret_key()
    assert first_value == "cached-jwt-value"

    # Verify it's in the cache
    assert "JWT_SECRET" in SecretsTable._cache
    assert SecretsTable._cache["JWT_SECRET"] == "cached-jwt-value"

    # Second retrieval - should use cache
    second_value = secrets_table.get_jwt_secret_key()
    assert second_value == "cached-jwt-value"


def test_get_secret_no_secret_value_field(secrets_table: SecretsTable):
    """Test that KeyError is raised when secret has no secretValue field."""
    # Insert a malformed item without secretValue
    secrets_table.table.put_item(
        Item={
            "secretKey": "JWT_SECRET",
            "description": "Missing secretValue",
            "updatedAt": "2025-01-01T00:00:00Z",
        }
    )

    with pytest.raises(KeyError) as exc_info:
        secrets_table.get_jwt_secret_key()
    assert "JWT_SECRET" in str(exc_info.value)
