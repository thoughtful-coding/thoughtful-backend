import logging
import typing
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from aws_src_sample.models.user_progress_models import (
    SectionCompletionInputModel,
    UserProgressModel,
)
from aws_src_sample.utils.base_types import IsoTimestamp, SectionId, UserId

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class UserProgressTable:
    """
    A wrapper class to abstract DynamoDB operations for the UserProgressTable.
    """

    def __init__(self, table_name: str) -> None:
        self.client = boto3.resource("dynamodb")
        self.table = self.client.Table(table_name)

    def get_user_progress(self, user_id: UserId) -> typing.Optional[UserProgressModel]:
        """
        Retrieves a user's progress from DynamoDB.
        :param user_id: The ID of the user.
        :return: UserProgressModel instance if found, else None.
        """
        _LOGGER.info("Fetching progress for user_id: %s", user_id)
        try:
            response = self.table.get_item(Key={"userId": user_id})
            item = response.get("Item")
            if item:
                return UserProgressModel.model_validate(item)
            _LOGGER.info("No progress found for user_id: %s", user_id)
            return None
        except ClientError as e:
            _LOGGER.exception(
                "Failed to get progress for user_id %s from DynamoDB: %s", user_id, e.response["Error"]["Message"]
            )
            raise
        except Exception as e_val:
            _LOGGER.exception("Failed to validate progress data for user_id %s from DynamoDB: %s", user_id, str(e_val))
            return None

    def get_unit_progress_for_user(
        self, user_id: UserId, unit_id_prefix: str
    ) -> typing.Dict[str, dict[SectionId, IsoTimestamp]]:
        """
        Fetches a user's completed sections for lessons belonging to a specific unit.
        Args:
            user_id: The ID of the user.
            unit_id_prefix: The prefix for lesson IDs in this unit (e.g., "00_intro").
        Returns:
            A dictionary where keys are full lesson IDs (e.g., "00_intro/lesson_1")
            and values are sections -> timestamps
        """
        user_progress = self.get_user_progress(user_id)
        if not user_progress or not user_progress.completion:
            return {}

        unit_completions: typing.Dict[str, dict[SectionId, IsoTimestamp]] = {}
        for lesson_id_path, sections_completed_map in user_progress.completion.items():
            # lesson_id_path is like "00_intro/lesson_1"
            # unit_id_prefix is like "00_intro"
            if lesson_id_path.startswith(unit_id_prefix + "/"):  # Ensure it's a lesson within the unit
                unit_completions[lesson_id_path] = sections_completed_map
        return unit_completions

    def update_user_progress(
        self,
        user_id: UserId,
        completions_to_add: list[SectionCompletionInputModel],
    ) -> UserProgressModel:
        """
        Updates user's progress by adding new section completions.
        Only adds completions for sections that haven't been completed before (preserves first completion time).
        Server sets the timeFirstCompleted timestamp for new completions.
        :param user_id: The ID of the user.
        :param completions_to_add: A list of SectionCompletionInputModel objects.
        :return: The updated UserProgressModel.
        """
        _LOGGER.info("Updating progress for user_id: %s with %d new completions.", user_id, len(completions_to_add))

        # Server generates the timestamp for when these completions are processed
        completion_timestamp = datetime.now(timezone.utc).isoformat()

        if not completions_to_add:
            # Just ensure user exists with empty completion map
            try:
                response = self.table.update_item(
                    Key={"userId": user_id},
                    UpdateExpression="SET completion = if_not_exists(completion, :empty_map)",
                    ExpressionAttributeValues={":empty_map": {}},
                    ReturnValues="ALL_NEW",
                )
                updated_item = response.get("Attributes", {})
                if updated_item:
                    return UserProgressModel.model_validate(updated_item)

                # Fallback: create new user
                new_progress = UserProgressModel(userId=user_id)
                self.table.put_item(Item=new_progress.model_dump())
                return new_progress
            except ClientError as e:
                _LOGGER.exception(
                    "Failed to ensure user exists for user_id %s: %s", user_id, e.response["Error"]["Message"]
                )
                raise

        try:
            # Step 1: Ensure completion map exists
            self.table.update_item(
                Key={"userId": user_id},
                UpdateExpression="SET completion = if_not_exists(completion, :empty_map)",
                ExpressionAttributeValues={":empty_map": {}},
                ReturnValues="NONE",
            )

            # Step 2: Initialize lesson maps for unique lessons
            unique_lessons = list(set(comp.lessonId for comp in completions_to_add))

            if unique_lessons:
                lesson_expressions = []
                lesson_values = {}
                lesson_names = {}

                for i, lesson_id in enumerate(unique_lessons):
                    lesson_placeholder = f"#lesson{i}"
                    lesson_map_placeholder = f":empty_lesson_map{i}"

                    lesson_names[lesson_placeholder] = lesson_id
                    lesson_expressions.append(
                        f"completion.{lesson_placeholder} = if_not_exists(completion.{lesson_placeholder}, {lesson_map_placeholder})"
                    )
                    lesson_values[lesson_map_placeholder] = {}

                self.table.update_item(
                    Key={"userId": user_id},
                    UpdateExpression="SET " + ", ".join(lesson_expressions),
                    ExpressionAttributeValues=lesson_values,
                    ExpressionAttributeNames=lesson_names,
                    ReturnValues="NONE",
                )

            # Step 3: Set individual section completion times
            section_expressions = []
            section_values = {}
            section_names = {}

            for i, comp in enumerate(completions_to_add):
                lesson_placeholder = f"#lesson{i}"
                section_placeholder = f"#section{i}"
                timestamp_placeholder = f":timestamp{i}"

                section_names[lesson_placeholder] = comp.lessonId
                section_names[section_placeholder] = comp.sectionId
                section_values[timestamp_placeholder] = completion_timestamp

                section_expressions.append(
                    f"completion.{lesson_placeholder}.{section_placeholder} = if_not_exists(completion.{lesson_placeholder}.{section_placeholder}, {timestamp_placeholder})"
                )

            response = self.table.update_item(
                Key={"userId": user_id},
                UpdateExpression="SET " + ", ".join(section_expressions),
                ExpressionAttributeValues=section_values,
                ExpressionAttributeNames=section_names,
                ReturnValues="ALL_NEW",
            )

            updated_item = response.get("Attributes", {})
            if not updated_item:
                _LOGGER.error("UpdateItem did not return attributes for user_id: %s", user_id)
                return self.get_user_progress(user_id) or UserProgressModel(userId=user_id)

            return UserProgressModel.model_validate(updated_item)

        except ClientError as e:
            _LOGGER.exception(
                "Failed to update progress for user_id %s in DynamoDB: %s", user_id, e.response["Error"]["Message"]
            )
            raise
        except Exception as e_val:
            _LOGGER.exception("Failed to validate updated progress data for user_id %s: %s", user_id, str(e_val))
            raise
