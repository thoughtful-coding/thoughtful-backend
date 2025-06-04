import logging
import typing
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from pydantic import ValidationError

from aws_src_sample.models.user_progress_models import (
    SectionCompletionInputModel,
    UserUnitProgressModel,
)
from aws_src_sample.utils.base_types import IsoTimestamp, UnitId, UserId

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class UserProgressTable:
    """
    A wrapper class to abstract DynamoDB operations for the UserProgressTable.
    Assumes table has PK: userId, SK: unitId.
    """

    def __init__(self, table_name: str) -> None:
        self.client = boto3.resource("dynamodb")
        self.table = self.client.Table(table_name)

    def get_user_unit_progress(self, user_id: UserId, unit_id: UnitId) -> typing.Optional[UserUnitProgressModel]:
        """
        Retrieves a user's progress for a specific unit from DynamoDB.
        :param user_id: The ID of the user.
        :param unit_id: The ID of the unit.
        :return: UserUnitProgressModel instance if found, else None.
        """
        _LOGGER.info(f"Fetching progress for user_id: {user_id}, unit_id: {unit_id}")
        try:
            response = self.table.get_item(Key={"userId": user_id, "unitId": unit_id})
            item_data = response.get("Item")
            if item_data:
                return UserUnitProgressModel.model_validate(item_data)
            _LOGGER.info(f"No progress found for user_id: {user_id}, unit_id: {unit_id}")
            return None
        except ClientError as e:
            _LOGGER.error(f"Failed for user_id {user_id}, unit_id {unit_id}: {e.response['Error']['Message']}")
            raise
        except ValidationError as ve:
            _LOGGER.error(f"Failed to validate data for user_id {user_id}, unit_id {unit_id}: {ve}", exc_info=True)
            return None

    def get_all_unit_progress_for_user(self, user_id: UserId) -> list[UserUnitProgressModel]:
        """
        Retrieves all unit progress items for a given user by querying on the partition key.
        """
        _LOGGER.info(f"Fetching all unit progress for user_id: {user_id}")
        progress_items: list[UserUnitProgressModel] = []
        try:
            response = self.table.query(KeyConditionExpression=Key("userId").eq(user_id))
            for item_data in response.get("Items", []):
                try:
                    progress_items.append(UserUnitProgressModel.model_validate(item_data))
                except ValidationError as ve:
                    _LOGGER.warning(f"Skipping invalid progress item for user {user_id}: {item_data}. Error: {ve}")

            # Handle pagination if there could be many unit progresses for a single user
            # (though less likely than many sections within a single progress item)
            while "LastEvaluatedKey" in response:
                _LOGGER.info(f"Fetching next page of unit progress for user_id: {user_id}")
                response = self.table.query(
                    KeyConditionExpression=Key("userId").eq(user_id),
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                for item_data in response.get("Items", []):
                    try:
                        progress_items.append(UserUnitProgressModel.model_validate(item_data))
                    except ValidationError as ve:
                        _LOGGER.warning(f"Skipping invalid item for user {user_id}: {item_data}. Error: {ve}")

        except ClientError as e:
            _LOGGER.error(f"Failed to query all unit progress for user {user_id}: {e.response['Error']['Message']}")
            raise
        return progress_items

    def batch_update_user_progress(
        self,
        user_id: UserId,
        completions_to_add: list[SectionCompletionInputModel],
    ) -> dict[UnitId, UserUnitProgressModel]:
        """
        Updates user's progress by adding new section completions.
        Each SectionCompletionInputModel now includes unit_id, lesson_id, and section_id.
        This method performs a get-modify-put for each affected unit.

        :param user_id: The ID of the user.
        :param completions_to_add: A list of SectionCompletionInputModel objects.
        :return: A dictionary mapping unitId to the updated UserUnitProgressModel for affected units.
        """
        _LOGGER.info(f"Batch updating progress for user_id: {user_id} with {len(completions_to_add)} section inputs.")

        completion_timestamp = IsoTimestamp(datetime.now(timezone.utc).isoformat())
        updated_units_data: dict[UnitId, UserUnitProgressModel] = {}

        # Group completions by unit_id to process each unit's item once
        updates_by_unit: dict[UnitId, list[SectionCompletionInputModel]] = {}
        for comp_input in completions_to_add:
            updates_by_unit.setdefault(comp_input.unitId, []).append(comp_input)

        for unit_id, unit_specific_completions in updates_by_unit.items():
            _LOGGER.debug(f"Processing {unit_id} for user {user_id} w/ {len(unit_specific_completions)} updates.")

            # Get existing progress for this specific unit, or create a new one
            current_unit_progress = self.get_user_unit_progress(user_id, unit_id)

            if current_unit_progress:
                progress_model_to_update = current_unit_progress
            else:
                _LOGGER.info(f"No existing progress for user {user_id}, unit {unit_id}. Creating new item.")
                progress_model_to_update = UserUnitProgressModel(
                    userId=user_id,
                    unitId=unit_id,
                    completion={},
                )

            unit_was_modified = False
            for comp_input in unit_specific_completions:
                lesson_id = comp_input.lessonId
                section_id = comp_input.sectionId

                if lesson_id not in progress_model_to_update.completion:
                    progress_model_to_update.completion[lesson_id] = {}

                if section_id not in progress_model_to_update.completion[lesson_id]:
                    progress_model_to_update.completion[lesson_id][section_id] = completion_timestamp
                    unit_was_modified = True
                    _LOGGER.debug(f"Marked section {unit_id}/{lesson_id}/{section_id} as complete for user {user_id}.")
                else:
                    _LOGGER.debug(f"Section {unit_id}/{lesson_id}/{section_id} already marked for user {user_id}.")

            if unit_was_modified:
                try:
                    item_to_put = progress_model_to_update.model_dump(by_alias=True, exclude_none=True)
                    self.table.put_item(Item=item_to_put)
                    updated_units_data[unit_id] = progress_model_to_update
                    _LOGGER.info(f"Successfully updated unit progress for user {user_id}, unit {unit_id}.")
                except ClientError as e:
                    _LOGGER.error(f"Failed to updatefor {user_id}, unit {unit_id}: {e.response['Error']['Message']}")
            elif current_unit_progress:
                updated_units_data[unit_id] = current_unit_progress

        _LOGGER.info(f"Batch update for user {user_id} processed. {len(updated_units_data)} unit(s) affected/returned.")
        return updated_units_data
