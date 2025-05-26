# src/aws_src_sample/dynamodb/throttling_store_table.py
import logging
import typing

import boto3
from botocore.exceptions import ClientError

_LOGGER = logging.getLogger(__name__)

# Constants for SK prefixes, could be part of the class or module level
MINUTE_TRACK_PREFIX = "MINUTE_TRACK#LATEST"
DAILY_COUNT_PREFIX = "DAILY_COUNT#"


class ThrottlingStoreTable:
    """
    Data Abstraction Layer for interacting with the ThrottlingStore DynamoDB table.
    """

    def __init__(self, table_name: str) -> None:  # Allow passing resource for testing
        self.client = boto3.resource("dynamodb")
        self.table = self.client.Table(table_name)

    def _get_user_pk(self, user_id: str, action_type: str) -> str:
        return f"USER#{user_id}#{action_type}"

    def _get_global_pk(self, action_type: str) -> str:
        return f"GLOBAL#{action_type}"

    def get_user_minute_timestamp(self, user_id: str, action_type: str) -> typing.Optional[int]:
        """
        Retrieves the last call timestamp for a user's minute limit.
        """
        pk = self._get_user_pk(user_id, action_type)
        sk = MINUTE_TRACK_PREFIX
        try:
            response = self.table.get_item(Key={"entityActionId": pk, "periodType#periodIdentifier": sk})
            item = response.get("Item")
            if item and "lastCallTimestamp" in item:
                return int(item["lastCallTimestamp"])
            return None
        except ClientError as e:
            _LOGGER.error(f"Error getting user minute timestamp for {pk}: {e.response['Error']['Message']}")
            raise  # Or handle more gracefully, e.g., return None and let caller decide to fail open/closed

    def get_user_daily_count(self, user_id: str, action_type: str, date_str: str) -> int:
        """
        Retrieves the call count for a user's daily limit.
        """
        pk = self._get_user_pk(user_id, action_type)
        sk = f"{DAILY_COUNT_PREFIX}{date_str}"
        try:
            response = self.table.get_item(Key={"entityActionId": pk, "periodType#periodIdentifier": sk})
            item = response.get("Item")
            return int(item["callCount"]) if item and "callCount" in item else 0
        except ClientError as e:
            _LOGGER.error(f"Error getting user daily count for {pk} on {date_str}: {e.response['Error']['Message']}")
            raise

    def get_global_daily_count(self, action_type: str, date_str: str) -> int:
        """
        Retrieves the global call count for an action's daily limit.
        """
        pk = self._get_global_pk(action_type)
        sk = f"{DAILY_COUNT_PREFIX}{date_str}"
        try:
            response = self.table.get_item(Key={"entityActionId": pk, "periodType#periodIdentifier": sk})
            item = response.get("Item")
            return int(item["callCount"]) if item and "callCount" in item else 0
        except ClientError as e:
            _LOGGER.error(f"Error getting global daily count for {pk} on {date_str}: {e.response['Error']['Message']}")
            raise

    def update_user_minute_timestamp(self, user_id: str, action_type: str, timestamp_epoch: int):
        """
        Updates the last call timestamp for a user's minute limit.
        """
        pk = self._get_user_pk(user_id, action_type)
        sk = MINUTE_TRACK_PREFIX
        try:
            self.table.update_item(
                Key={"entityActionId": pk, "periodType#periodIdentifier": sk},
                UpdateExpression="SET lastCallTimestamp = :ts",
                ExpressionAttributeValues={":ts": timestamp_epoch},
            )
            _LOGGER.debug(f"Updated user minute timestamp for {pk} to {timestamp_epoch}")
        except ClientError as e:
            _LOGGER.error(f"Error updating user minute timestamp for {pk}: {e.response['Error']['Message']}")
            raise

    def increment_user_daily_count(self, user_id: str, action_type: str, date_str: str, ttl_epoch: int) -> int:
        """
        Atomically increments a user's daily call count and sets TTL. Returns the new count.
        """
        pk = self._get_user_pk(user_id, action_type)
        sk = f"{DAILY_COUNT_PREFIX}{date_str}"
        try:
            response = self.table.update_item(
                Key={"entityActionId": pk, "periodType#periodIdentifier": sk},
                UpdateExpression="ADD callCount :inc SET ttl = :ttl_val",
                ExpressionAttributeValues={":inc": 1, ":ttl_val": ttl_epoch},
                ReturnValues="UPDATED_NEW",
            )
            new_count = int(response["Attributes"]["callCount"])
            _LOGGER.debug(f"Incremented user daily count for {pk} on {date_str} to {new_count}")
            return new_count
        except ClientError as e:
            _LOGGER.error(
                f"Error incrementing user daily count for {pk} on {date_str}: {e.response['Error']['Message']}"
            )
            raise

    def increment_global_daily_count(
        self, action_type: str, date_str: str, ttl_epoch: int, limit: int
    ) -> typing.Optional[int]:
        """
        Atomically increments the global daily call count with a conditional update.
        Returns the new count if successful and limit not breached by this increment,
        None if the conditional check failed (limit was already reached or breached).
        """
        pk = self._get_global_pk(action_type)
        sk = f"{DAILY_COUNT_PREFIX}{date_str}"
        try:
            response = self.table.update_item(
                Key={"entityActionId": pk, "periodType#periodIdentifier": sk},
                UpdateExpression="ADD callCount :inc SET ttl = :ttl_val",
                ExpressionAttributeValues={":inc": 1, ":limit_val": limit, ":ttl_val": ttl_epoch},
                ConditionExpression="attribute_not_exists(callCount) OR callCount < :limit_val",
                ReturnValues="UPDATED_NEW",
            )
            new_count = int(response["Attributes"]["callCount"])
            _LOGGER.debug(f"Incremented global daily count for {pk} on {date_str} to {new_count}")
            return new_count
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                _LOGGER.warning(
                    f"Conditional check failed for global daily count {pk} on {date_str}. Limit likely reached."
                )
                return None  # Indicates limit was hit or already over
            _LOGGER.error(
                f"Error incrementing global daily count for {pk} on {date_str}: {e.response['Error']['Message']}"
            )
            raise
