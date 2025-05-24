import logging
import typing
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class SectionCompletionModel(BaseModel):
    lessonId: str
    sectionId: str


class BatchCompletionsInputModel(BaseModel):
    completions: list[SectionCompletionModel]


class UserProgressResponseModel(BaseModel):
    userId: str
    # completion structure: lessonId -> sectionId -> timeFirstCompleted
    completion: dict[str, dict[str, str]] = Field(default_factory=dict)


class UserProgressTable:
    """
    A wrapper class to abstract DynamoDB operations for the UserProgressTable.
    """

    def __init__(self, table_name: str) -> None:
        self.client = boto3.resource("dynamodb")
        self.table = self.client.Table(table_name)

    def get_progress(self, user_id: str) -> typing.Optional[UserProgressResponseModel]:
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
                return UserProgressResponseModel.model_validate(item)
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

    def update_progress(
        self,
        user_id: str,
        completions_to_add: list[SectionCompletionModel],
    ) -> UserProgressResponseModel:
        """
        Updates user's progress by adding new section completions.
        Only adds completions for sections that haven't been completed before (preserves first completion time).
        Server sets the timeFirstCompleted timestamp for new completions.
        :param user_id: The ID of the user.
        :param completions_to_add: A list of SectionCompletionModel objects.
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
                    return UserProgressResponseModel.model_validate(updated_item)

                # Fallback: create new user
                new_progress = UserProgressResponseModel(userId=user_id)
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
                return self.get_progress(user_id) or UserProgressResponseModel(userId=user_id)

            return UserProgressResponseModel.model_validate(updated_item)

        except ClientError as e:
            _LOGGER.exception(
                "Failed to update progress for user_id %s in DynamoDB: %s", user_id, e.response["Error"]["Message"]
            )
            raise
        except Exception as e_val:
            _LOGGER.exception("Failed to validate updated progress data for user_id %s: %s", user_id, str(e_val))
            raise
