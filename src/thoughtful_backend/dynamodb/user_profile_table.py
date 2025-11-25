import logging
import typing
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from pydantic import ValidationError

from thoughtful_backend.models.user_profile_models import UserProfileModel
from thoughtful_backend.utils.base_types import IsoTimestamp, UserId

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class UserProfileTable:
    """
    Data Abstraction Layer for interacting with the UserProfile DynamoDB table.
    Manages user-level metadata such as initialization status, timestamps, and preferences.

    Table Schema:
      - PK: userId (user's email address)
    """

    def __init__(self, table_name: str) -> None:
        self.client = boto3.resource("dynamodb")
        self.table = self.client.Table(table_name)

    def get_profile(self, user_id: UserId) -> typing.Optional[UserProfileModel]:
        """
        Retrieves a user's profile from DynamoDB.

        :param user_id: The ID of the user.
        :return: UserProfileModel instance if found, else None.
        """
        _LOGGER.debug(f"Fetching profile for user_id: {user_id}")
        try:
            response = self.table.get_item(Key={"userId": user_id})
            item_data = response.get("Item")
            if item_data:
                return UserProfileModel.model_validate(item_data)
            _LOGGER.debug(f"No profile found for user_id: {user_id}")
            return None
        except ClientError as e:
            _LOGGER.error(f"Failed to get profile for user_id {user_id}: {e.response['Error']['Message']}")
            raise
        except ValidationError as ve:
            _LOGGER.error(f"Failed to validate profile data for user_id {user_id}: {ve}", exc_info=True)
            return None

    def create_or_update_profile(
        self,
        user_id: UserId,
        initialized: typing.Optional[bool] = None,
        created_at: typing.Optional[IsoTimestamp] = None,
        last_login_at: typing.Optional[IsoTimestamp] = None,
        preferences: typing.Optional[dict[str, typing.Any]] = None,
        metadata: typing.Optional[dict[str, typing.Any]] = None,
    ) -> bool:
        """
        Creates or updates a user profile in DynamoDB.
        Only provided fields will be updated; None values are ignored.

        :param user_id: The ID of the user.
        :param initialized: Whether user has been initialized.
        :param created_at: ISO timestamp of when user first logged in.
        :param last_login_at: ISO timestamp of most recent login.
        :param preferences: User preferences dictionary.
        :param metadata: Arbitrary metadata dictionary.
        :return: True if successful, False otherwise.
        """
        _LOGGER.info(f"Creating/updating profile for user_id: {user_id}")

        # Build update expression dynamically based on provided fields
        update_parts = []
        expression_attribute_names = {}
        expression_attribute_values = {}

        if initialized is not None:
            update_parts.append("#initialized = :initialized")
            expression_attribute_names["#initialized"] = "initialized"
            expression_attribute_values[":initialized"] = initialized

        if created_at is not None:
            update_parts.append("#createdAt = :createdAt")
            expression_attribute_names["#createdAt"] = "createdAt"
            expression_attribute_values[":createdAt"] = created_at

        if last_login_at is not None:
            update_parts.append("#lastLoginAt = :lastLoginAt")
            expression_attribute_names["#lastLoginAt"] = "lastLoginAt"
            expression_attribute_values[":lastLoginAt"] = last_login_at

        if preferences is not None:
            update_parts.append("#preferences = :preferences")
            expression_attribute_names["#preferences"] = "preferences"
            expression_attribute_values[":preferences"] = preferences

        if metadata is not None:
            update_parts.append("#metadata = :metadata")
            expression_attribute_names["#metadata"] = "metadata"
            expression_attribute_values[":metadata"] = metadata

        if not update_parts:
            _LOGGER.warning(f"No fields provided to update for user_id {user_id}")
            return False

        update_expression = "SET " + ", ".join(update_parts)

        try:
            self.table.update_item(
                Key={"userId": user_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
            )
            _LOGGER.info(f"Successfully updated profile for user_id: {user_id}")
            return True
        except ClientError as e:
            _LOGGER.error(
                f"Error updating profile for user_id {user_id}: {e.response['Error']['Message']}", exc_info=True
            )
            return False

    def update_last_login(self, user_id: UserId) -> bool:
        """
        Updates the lastLoginAt timestamp for a user.

        :param user_id: The ID of the user.
        :return: True if successful, False otherwise.
        """
        timestamp = IsoTimestamp(datetime.now(timezone.utc).isoformat())
        return self.create_or_update_profile(user_id=user_id, last_login_at=timestamp)

    def is_user_initialized(self, user_id: UserId) -> bool:
        """
        Checks if a user has been initialized (first-time login hook completed).

        :param user_id: The ID of the user.
        :return: True if user has been initialized, False otherwise.
        """
        _LOGGER.debug(f"Checking initialization status for user_id: {user_id}")
        profile = self.get_profile(user_id)
        if profile and profile.initialized:
            _LOGGER.debug(f"User {user_id} is initialized.")
            return True
        _LOGGER.debug(f"User {user_id} is not initialized.")
        return False

    def mark_user_initialized(self, user_id: UserId) -> bool:
        """
        Marks a user as initialized after first-login setup.
        Also sets createdAt if this is the first time the profile is being created.

        :param user_id: The ID of the user.
        :return: True if successful, False otherwise.
        """
        _LOGGER.info(f"Marking user {user_id} as initialized.")
        timestamp = IsoTimestamp(datetime.now(timezone.utc).isoformat())

        # Check if profile exists to decide whether to set createdAt
        existing_profile = self.get_profile(user_id)
        if existing_profile:
            # Profile exists, just update initialized flag
            return self.create_or_update_profile(user_id=user_id, initialized=True, last_login_at=timestamp)
        else:
            # Profile doesn't exist, create it with createdAt
            return self.create_or_update_profile(
                user_id=user_id, initialized=True, created_at=timestamp, last_login_at=timestamp
            )
