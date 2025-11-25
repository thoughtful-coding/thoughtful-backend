import os
from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws

from thoughtful_backend.dynamodb.user_profile_table import UserProfileTable
from thoughtful_backend.utils.base_types import IsoTimestamp, UserId

REGION = "us-west-1"
TABLE_NAME = "UserProfileTable"


@pytest.fixture
def dynamodb_profile_table(aws_credentials):
    """Creates the mocked UserProfile table."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "userId", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "userId", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


@pytest.fixture
def user_profile_table(dynamodb_profile_table) -> UserProfileTable:
    """Returns a UserProfileTable instance using the mocked table."""
    return UserProfileTable(TABLE_NAME)


# Helper to cast strings to UserId for test readability
def as_userid(s: str) -> UserId:
    return UserId(s)


# --- Test Cases ---


def test_get_profile_not_exists(user_profile_table: UserProfileTable):
    """Tests that get_profile returns None when profile doesn't exist."""
    user_id = as_userid("nonexistent@example.com")
    profile = user_profile_table.get_profile(user_id)
    assert profile is None


def test_create_or_update_profile_single_field(user_profile_table: UserProfileTable):
    """Tests creating a profile with a single field."""
    user_id = as_userid("user1@example.com")

    # Create profile with only initialized field
    success = user_profile_table.create_or_update_profile(user_id=user_id, initialized=True)
    assert success is True

    # Verify profile was created
    profile = user_profile_table.get_profile(user_id)
    assert profile is not None
    assert profile.userId == user_id
    assert profile.initialized is True
    assert profile.createdAt is None
    assert profile.lastLoginAt is None
    assert profile.preferences is None
    assert profile.metadata is None


def test_create_or_update_profile_multiple_fields(user_profile_table: UserProfileTable):
    """Tests creating a profile with multiple fields."""
    user_id = as_userid("user2@example.com")
    created_at = IsoTimestamp(datetime.now(timezone.utc).isoformat())
    last_login_at = IsoTimestamp(datetime.now(timezone.utc).isoformat())
    preferences = {"theme": "dark", "language": "en"}
    metadata = {"source": "google_oauth", "version": "1.0"}

    success = user_profile_table.create_or_update_profile(
        user_id=user_id,
        initialized=True,
        created_at=created_at,
        last_login_at=last_login_at,
        preferences=preferences,
        metadata=metadata,
    )
    assert success is True

    # Verify all fields were saved
    profile = user_profile_table.get_profile(user_id)
    assert profile is not None
    assert profile.userId == user_id
    assert profile.initialized is True
    assert profile.createdAt == created_at
    assert profile.lastLoginAt == last_login_at
    assert profile.preferences == preferences
    assert profile.metadata == metadata


def test_create_or_update_profile_update_existing(user_profile_table: UserProfileTable):
    """Tests updating an existing profile with new values."""
    user_id = as_userid("user3@example.com")

    # Create initial profile
    user_profile_table.create_or_update_profile(user_id=user_id, initialized=False)

    # Update with new values
    new_preferences = {"theme": "light"}
    success = user_profile_table.create_or_update_profile(
        user_id=user_id, initialized=True, preferences=new_preferences
    )
    assert success is True

    # Verify update was applied
    profile = user_profile_table.get_profile(user_id)
    assert profile is not None
    assert profile.initialized is True
    assert profile.preferences == new_preferences


def test_create_or_update_profile_no_fields_provided(user_profile_table: UserProfileTable):
    """Tests that create_or_update_profile returns False when no fields are provided."""
    user_id = as_userid("user4@example.com")

    # Call with no field updates
    success = user_profile_table.create_or_update_profile(user_id=user_id)
    assert success is False


def test_update_last_login(user_profile_table: UserProfileTable):
    """Tests updating the lastLoginAt timestamp."""
    user_id = as_userid("user5@example.com")

    # Update last login (creates profile if it doesn't exist)
    success = user_profile_table.update_last_login(user_id)
    assert success is True

    # Verify lastLoginAt was set
    profile = user_profile_table.get_profile(user_id)
    assert profile is not None
    assert profile.lastLoginAt is not None

    # Store the first timestamp
    first_login = profile.lastLoginAt

    # Update again and verify timestamp changed
    success = user_profile_table.update_last_login(user_id)
    assert success is True

    profile = user_profile_table.get_profile(user_id)
    assert profile.lastLoginAt is not None
    assert profile.lastLoginAt >= first_login  # Should be same or later


def test_is_user_initialized_not_exists(user_profile_table: UserProfileTable):
    """Tests that is_user_initialized returns False when profile doesn't exist."""
    user_id = as_userid("nonexistent@example.com")
    assert user_profile_table.is_user_initialized(user_id) is False


def test_is_user_initialized_false(user_profile_table: UserProfileTable):
    """Tests that is_user_initialized returns False when initialized is False."""
    user_id = as_userid("user6@example.com")
    user_profile_table.create_or_update_profile(user_id=user_id, initialized=False)

    assert user_profile_table.is_user_initialized(user_id) is False


def test_is_user_initialized_true(user_profile_table: UserProfileTable):
    """Tests that is_user_initialized returns True when initialized is True."""
    user_id = as_userid("user7@example.com")
    user_profile_table.create_or_update_profile(user_id=user_id, initialized=True)

    assert user_profile_table.is_user_initialized(user_id) is True


def test_mark_user_initialized_new_user(user_profile_table: UserProfileTable):
    """Tests marking a new user as initialized (creates profile with createdAt)."""
    user_id = as_userid("newuser@example.com")

    # Verify user doesn't exist
    assert user_profile_table.is_user_initialized(user_id) is False

    # Mark as initialized
    success = user_profile_table.mark_user_initialized(user_id)
    assert success is True

    # Verify profile was created with all timestamps
    profile = user_profile_table.get_profile(user_id)
    assert profile is not None
    assert profile.initialized is True
    assert profile.createdAt is not None
    assert profile.lastLoginAt is not None


def test_mark_user_initialized_existing_user(user_profile_table: UserProfileTable):
    """Tests marking an existing user as initialized (doesn't overwrite createdAt)."""
    user_id = as_userid("existinguser@example.com")
    created_at = IsoTimestamp(datetime.now(timezone.utc).isoformat())

    # Create existing profile with createdAt
    user_profile_table.create_or_update_profile(user_id=user_id, initialized=False, created_at=created_at)

    # Mark as initialized
    success = user_profile_table.mark_user_initialized(user_id)
    assert success is True

    # Verify initialized was updated but createdAt was preserved
    profile = user_profile_table.get_profile(user_id)
    assert profile is not None
    assert profile.initialized is True
    assert profile.createdAt == created_at  # Original createdAt preserved
    assert profile.lastLoginAt is not None


def test_create_or_update_profile_partial_updates(user_profile_table: UserProfileTable):
    """Tests that partial updates only modify specified fields."""
    user_id = as_userid("user8@example.com")

    # Create profile with multiple fields
    user_profile_table.create_or_update_profile(
        user_id=user_id, initialized=False, preferences={"theme": "dark"}, metadata={"version": "1.0"}
    )

    # Update only preferences
    new_preferences = {"theme": "light", "fontSize": "large"}
    user_profile_table.create_or_update_profile(user_id=user_id, preferences=new_preferences)

    # Verify preferences changed but other fields remain
    profile = user_profile_table.get_profile(user_id)
    assert profile is not None
    assert profile.initialized is False  # Unchanged
    assert profile.preferences == new_preferences  # Updated
    assert profile.metadata == {"version": "1.0"}  # Unchanged


def test_create_or_update_profile_boolean_false_value(user_profile_table: UserProfileTable):
    """Tests that initialized=False is properly stored (not treated as None)."""
    user_id = as_userid("user9@example.com")

    # Create with initialized=False
    success = user_profile_table.create_or_update_profile(user_id=user_id, initialized=False)
    assert success is True

    # Verify False was stored
    profile = user_profile_table.get_profile(user_id)
    assert profile is not None
    assert profile.initialized is False

    # Update to True
    user_profile_table.create_or_update_profile(user_id=user_id, initialized=True)

    # Verify update worked
    profile = user_profile_table.get_profile(user_id)
    assert profile.initialized is True


def test_preferences_and_metadata_complex_types(user_profile_table: UserProfileTable):
    """Tests that preferences and metadata can store complex nested structures."""
    user_id = as_userid("user10@example.com")

    complex_preferences = {
        "theme": "dark",
        "notifications": {"email": True, "push": False, "frequency": "daily"},
        "ui": {"sidebarCollapsed": True, "fontSize": 14},
    }

    complex_metadata = {
        "loginHistory": [{"timestamp": "2025-01-01T00:00:00Z", "ip": "192.168.1.1"}],
        "flags": {"betaTester": True, "earlyAccess": False},
    }

    success = user_profile_table.create_or_update_profile(
        user_id=user_id, preferences=complex_preferences, metadata=complex_metadata
    )
    assert success is True

    # Verify complex structures are preserved
    profile = user_profile_table.get_profile(user_id)
    assert profile is not None
    assert profile.preferences == complex_preferences
    assert profile.metadata == complex_metadata
