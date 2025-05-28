import logging
import time
import typing
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError

from aws_src_sample.utils.base_types import UserId

_LOGGER = logging.getLogger(__name__)


ThrottleType = typing.Literal["REFLECTION_FEEDBACK_CHATBOT_API_CALL", "PRIMM_FEEDBACK_CHATBOT_API_CALL"]
LimitType = typing.Literal["USER_MINUTE_LIMIT", "USER_DAILY_LIMIT", "GLOBAL_DAILY_LIMIT"]


USER_MINUTE_LIMIT_SECONDS = 60
USER_DAILY_LIMIT_CALLS = 20
GLOBAL_DAILY_LIMIT_CALLS = 100

MINUTE_TRACK_SK_PREFIX = "MINUTE_TRACK#LATEST"
DAILY_COUNT_SK_PREFIX = "DAILY_COUNT#"


class ThrottleRateLimitExceededException(Exception):
    def __init__(self, limit_type: LimitType, message: str) -> None:
        self.limit_type = limit_type
        self.message = message
        super().__init__(message)


class ThrottledActionContext:
    def __init__(self, throttle_table: "ThrottleTable", user_id: UserId, throttle_type: ThrottleType):
        self.throttle_table = throttle_table
        self.user_id = user_id
        self.throttle_type: ThrottleType = throttle_type

        self.current_time_epoch: int = 0
        self.current_date_str: str = ""

        self.limits_passed_in_enter = False

    def __enter__(self):
        _LOGGER.debug(f"Entering throttled action context for user {self.user_id}, action {self.throttle_type}")
        self.current_time_epoch = int(time.time())
        self.current_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 1. Per-User Minute Limit Check
        last_call_ts = self.throttle_table.get_user_minute_timestamp(self.user_id, self.throttle_type)
        if last_call_ts is not None and (self.current_time_epoch - last_call_ts) < USER_MINUTE_LIMIT_SECONDS:
            msg = f"User {self.user_id} minute limit exceeded for {self.throttle_type}."
            _LOGGER.warning(msg)
            raise ThrottleRateLimitExceededException("USER_MINUTE_LIMIT", "Too many requests per minute.")

        # 2. Per-User Daily Limit Check
        user_daily_count = self.throttle_table.get_user_daily_count(
            self.user_id, self.throttle_type, self.current_date_str
        )
        if user_daily_count >= USER_DAILY_LIMIT_CALLS:
            msg = f"User {self.user_id} daily limit ({USER_DAILY_LIMIT_CALLS}) exceeded for {self.throttle_type}."
            _LOGGER.warning(msg)
            raise ThrottleRateLimitExceededException("USER_DAILY_LIMIT", "You've reached the daily usage.")

        # 3. Global Daily Limit Check
        global_daily_count = self.throttle_table.get_global_daily_count(self.throttle_type, self.current_date_str)
        if global_daily_count >= GLOBAL_DAILY_LIMIT_CALLS:
            msg = f"Global daily limit ({GLOBAL_DAILY_LIMIT_CALLS}) exceeded for {self.throttle_type}."
            _LOGGER.warning(msg)
            raise ThrottleRateLimitExceededException("GLOBAL_DAILY_LIMIT", "Service is experiencing high demand.")

        self.limits_passed_in_enter = True
        _LOGGER.debug(f"Throttling limits passed initial check for user {self.user_id}, action {self.throttle_type}")
        return self  # Allows using 'as alias' if needed, though not strictly necessary here

    def __exit__(self, exc_type, exc_val, exc_tb):
        _LOGGER.debug(f"Exiting throttled action for {self.user_id}, type {self.throttle_type}. Exception: {exc_type}")
        if self.limits_passed_in_enter and exc_type is None:
            # Main operation within the 'with' block was successful, so update counts
            _LOGGER.info(f"Operation successful for {self.user_id}, type {self.throttle_type}. Updating counts.")
            daily_item_ttl = self.throttle_table._get_ttl_for_daily_item(self.current_date_str)

            try:
                self.throttle_table.update_user_minute_timestamp(
                    self.user_id, self.throttle_type, self.current_time_epoch
                )
            except Exception as e:
                _LOGGER.error(f"Failed to update user minute timestamp in __exit__ for {self.user_id}: {e}")

            try:
                self.throttle_table.increment_user_daily_count(
                    self.user_id, self.throttle_type, self.current_date_str, daily_item_ttl
                )
            except Exception as e_user_daily_update:
                _LOGGER.error(f"Failed to update user daily count for {self.user_id}: {e_user_daily_update}")

            try:
                new_global_count = self.throttle_table.increment_global_daily_count(
                    self.throttle_type, self.current_date_str, daily_item_ttl, GLOBAL_DAILY_LIMIT_CALLS
                )
                if new_global_count is None:  # Conditional update failed
                    _LOGGER.warning(f"Global limit for {self.throttle_type} was hit by a concurrent request")
            except Exception as e_global_daily_update:
                _LOGGER.error(f"Failed to update global daily count in __exit__: {e_global_daily_update}")

        elif self.limits_passed_in_enter and exc_type is not None:
            # Throttling counts not update
            _LOGGER.info(f"Op failed in 'with' block for {self.user_id}, type {self.throttle_type} due to: {exc_val}")

        # Return False (or don't return anything) to re-raise any exception that occurred within the 'with' block.
        # This means if the chatbot_wrapper.call_api() fails, that exception will propagate.
        return False


class ThrottleTable:
    def __init__(self, table_name: str):
        self.client = boto3.resource("dynamodb")
        self.table = self.client.Table(table_name)
        _LOGGER.info(f"ThrottlingStoreTable DAL initialized for table: {table_name}")

    def _get_user_pk(self, user_id: UserId, throttle_type: ThrottleType) -> str:
        return f"USER#{user_id}#{throttle_type}"

    def _get_global_pk(self, throttle_type: ThrottleType) -> str:
        return f"GLOBAL#{throttle_type}"

    def _get_ttl_for_daily_item(self, date_str: str) -> int:
        """Calculates TTL for end of the given day + 1 hour buffer."""
        try:
            start_of_day_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            ttl_dt = start_of_day_dt + timedelta(days=1, hours=1)
            return int(ttl_dt.timestamp())
        except ValueError:
            _LOGGER.error(f"Invalid date_str format for TTL calculation: {date_str}")
            # Fallback TTL (e.g., 25 hours from now)
            return int((datetime.now(timezone.utc) + timedelta(hours=25)).timestamp())

    def get_user_minute_timestamp(self, user_id: UserId, throttle_type: ThrottleType) -> typing.Optional[int]:
        pk = self._get_user_pk(user_id, throttle_type)
        sk = MINUTE_TRACK_SK_PREFIX
        try:
            response = self.table.get_item(Key={"entityActionId": pk, "periodType#periodIdentifier": sk})
            item = response.get("Item")
            if item and "lastCallTimestamp" in item:
                return int(item["lastCallTimestamp"])
            return None
        except ClientError as e:
            _LOGGER.error(f"DynamoDB error getting user minute timestamp for {pk}: {e.response['Error']['Message']}")
            raise  # Re-raise to be handled by caller

    def get_user_daily_count(self, user_id: UserId, throttle_type: ThrottleType, date_str: str) -> int:
        pk = self._get_user_pk(user_id, throttle_type)
        sk = f"{DAILY_COUNT_SK_PREFIX}{date_str}"
        try:
            response = self.table.get_item(Key={"entityActionId": pk, "periodType#periodIdentifier": sk})
            item = response.get("Item")
            return int(item["callCount"]) if item and "callCount" in item else 0
        except ClientError as e:
            _LOGGER.error(
                f"DynamoDB error getting user daily count for {pk} on {date_str}: {e.response['Error']['Message']}"
            )
            raise

    def get_global_daily_count(self, throttle_type: ThrottleType, date_str: str) -> int:
        pk = self._get_global_pk(throttle_type)
        sk = f"{DAILY_COUNT_SK_PREFIX}{date_str}"
        try:
            response = self.table.get_item(Key={"entityActionId": pk, "periodType#periodIdentifier": sk})
            item = response.get("Item")
            return int(item["callCount"]) if item and "callCount" in item else 0
        except ClientError as e:
            _LOGGER.error(
                f"DynamoDB error getting global daily count for {pk} on {date_str}: {e.response['Error']['Message']}"
            )
            raise

    def update_user_minute_timestamp(self, user_id: UserId, throttle_type: ThrottleType, timestamp_epoch: int):
        pk = self._get_user_pk(user_id, throttle_type)
        sk = MINUTE_TRACK_SK_PREFIX
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

    def increment_user_daily_count(
        self, user_id: UserId, throttle_type: ThrottleType, date_str: str, ttl_epoch: int
    ) -> int:
        pk = self._get_user_pk(user_id, throttle_type)
        sk = f"{DAILY_COUNT_SK_PREFIX}{date_str}"
        try:
            response = self.table.update_item(
                Key={"entityActionId": pk, "periodType#periodIdentifier": sk},
                UpdateExpression="ADD callCount :inc SET #ttl_attr = :ttl_val",
                ExpressionAttributeNames={"#ttl_attr": "ttl"},
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
        self,
        throttle_type: ThrottleType,
        date_str: str,
        ttl_epoch: int,
        limit: int,
    ) -> typing.Optional[int]:
        pk = self._get_global_pk(throttle_type)
        sk = f"{DAILY_COUNT_SK_PREFIX}{date_str}"
        try:
            # Ensure :limit_val for ConditionExpression corresponds to the value *before* incrementing
            # If current count is limit-1, after ADD it becomes limit. Condition should be callCount < limit.
            # If attribute does not exist, callCount is effectively 0, so 0 < limit.
            response = self.table.update_item(
                Key={"entityActionId": pk, "periodType#periodIdentifier": sk},
                UpdateExpression="ADD callCount :inc SET #ttl_attr = :ttl_val",
                ExpressionAttributeNames={"#ttl_attr": "ttl"},
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
                    f"Conditional check failed for global daily count {pk} on {date_str}. Limit already reached or exceeded."
                )
                # Get the current count to confirm, if necessary, though it's already too high
                current_val_after_failed_incr = self.get_global_daily_count(throttle_type, date_str)
                _LOGGER.warning(
                    f"Current global count for {pk} on {date_str} is {current_val_after_failed_incr} after failed increment."
                )
                return None
            _LOGGER.error(
                f"Error incrementing global daily count for {pk} on {date_str}: {e.response['Error']['Message']}"
            )
            raise

    def throttle_action(self, user_id: UserId, throttle_type: ThrottleType) -> ThrottledActionContext:
        """
        Returns a context manager to handle throttling for the specified action.
        Raises ThrottlingRateLimitExceededException from __enter__ if limits are hit.
        """
        return ThrottledActionContext(self, user_id, throttle_type)
