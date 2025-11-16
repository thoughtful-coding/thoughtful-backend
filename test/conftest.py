"""
Pytest configuration and fixtures for all tests.

This file contains fixtures that are automatically available to all test files.
"""

import os
import typing

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Sets up environment variables required for all tests.

    This fixture runs once per test session and automatically applies to all tests
    (autouse=True). It sets environment variables that the application expects to be
    present at runtime.

    The fixture uses session scope for efficiency, as these env vars don't change
    between tests and don't need to be cleaned up (test process is isolated).
    """
    # AWS Configuration
    os.environ["AWS_REGION"] = "us-west-1"

    # DynamoDB Table Names
    os.environ["USER_PROGRESS_TABLE_NAME"] = "test-user-progress-table"
    os.environ["REFRESH_TOKEN_TABLE_NAME"] = "test-refresh-token-table"
    os.environ["LEARNING_ENTRIES_TABLE_NAME"] = "test-learning-entries-table"
    os.environ["PRIMM_SUBMISSIONS_TABLE_NAME"] = "test-primm-submissions-table"
    os.environ["USER_PERMISSIONS_TABLE_NAME"] = "test-user-permissions-table"
    os.environ["THROTTLING_TABLE_NAME"] = "test-throttle-table"
    os.environ["FIRST_SOLUTIONS_TABLE_NAME"] = "test-first-solutions-table"

    # AWS Secrets Manager ARNs
    os.environ["JWT_SECRET_ARN"] = "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-jwt-secret"
    os.environ["CHATBOT_API_KEY_SECRET_ARN"] = (
        "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-chatbot-api-key"
    )

    # Google OAuth Configuration
    os.environ["GOOGLE_CLIENT_ID"] = "test-google-client-id.apps.googleusercontent.com"

    # No explicit cleanup needed - pytest runs in isolated process
    yield


@pytest.fixture(scope="function")
def aws_credentials() -> typing.Iterator[None]:
    """
    Mocks AWS credentials for moto (AWS mocking library).

    This fixture is used by DynamoDB table tests that use the @mock_aws decorator
    or context manager from moto. It sets fake AWS credentials that moto expects.

    Note: This is different from the AWS_REGION set in setup_test_environment.
    - AWS_REGION: Used by application code via get_aws_region()
    - These credentials: Used by moto for AWS service mocking
    """
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-west-1"
    yield
    # Clean up after each test
    del os.environ["AWS_ACCESS_KEY_ID"]
    del os.environ["AWS_SECRET_ACCESS_KEY"]
    del os.environ["AWS_SECURITY_TOKEN"]
    del os.environ["AWS_SESSION_TOKEN"]
    del os.environ["AWS_DEFAULT_REGION"]
