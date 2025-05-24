import logging
import typing
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field, field_validator

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class SectionCompletionModel(BaseModel):
    lessonId: str
    sectionId: str
    timeFirstCompleted: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BatchCompletionsInputModel(BaseModel):
    completions: list[SectionCompletionModel]


class UserProgressModel(BaseModel):
    userId: str
    completion: dict[str, dict[str, str]] = Field(default_factory=dict)

    @field_validator("completion", mode="before")
    @classmethod
    def convert_dynamodb_maps(cls, v: typing.Any) -> typing.Any:
        """Handle DynamoDB data conversion if needed."""
        return v


class UserProgressTable:
    """
    A wrapper class to abstract DynamoDB operations for the UserProgressTable.
    """

    def __init__(self, table_name: str) -> None:
        self.client = boto3.resource("dynamodb")
        self.table = self.client.Table(table_name)

    def get_progress(self, user_id: str) -> typing.Optional[UserProgressModel]:
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

    def update_progress(self, user_id: str, completions_to_add: list[SectionCompletionModel]) -> UserProgressModel:
        """
        Updates user's progress by adding new section completions.
        Only adds completions for sections that haven't been completed before (preserves first completion time).
        :param user_id: The ID of the user.
        :param completions_to_add: A list of SectionCompletionModel objects.
        :return: The updated UserProgressModel.
        """
        _LOGGER.info("Updating progress for user_id: %s with %d new completions.", user_id, len(completions_to_add))

        if not completions_to_add:  # If no new completions, just ensure user exists
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
                # If item didn't exist, create a minimal one
                new_progress = UserProgressModel(userId=user_id)
                self.table.put_item(Item=new_progress.model_dump())
                return new_progress
            except ClientError as e:
                _LOGGER.exception(
                    "Failed to ensure user exists for user_id %s: %s", user_id, e.response["Error"]["Message"]
                )
                raise

        try:
            # Build SET expressions for new completions
            # Structure: completion.lessonId.sectionId = timeFirstCompleted (only if not exists)
            set_expressions: list[str] = ["completion = if_not_exists(completion, :empty_map)"]
            expression_attribute_values: dict[str, typing.Any] = {":empty_map": {}}
            expression_attribute_names: dict[str, str] = {}

            # Group by lesson for cleaner attribute naming
            lessons_processed = set()

            for i, comp in enumerate(completions_to_add):
                lesson_placeholder = f"#lesson_{i}"
                section_placeholder = f"#section_{i}"
                timestamp_placeholder = f":timestamp_{i}"

                expression_attribute_names[lesson_placeholder] = comp.lessonId
                expression_attribute_names[section_placeholder] = comp.sectionId
                expression_attribute_values[timestamp_placeholder] = comp.timeFirstCompleted

                # First ensure the lesson map exists if this is the first section we're adding for this lesson
                if comp.lessonId not in lessons_processed:
                    lesson_map_placeholder = f":empty_lesson_map_{len(lessons_processed)}"
                    set_expressions.append(
                        f"completion.{lesson_placeholder} = if_not_exists(completion.{lesson_placeholder}, {lesson_map_placeholder})"
                    )
                    expression_attribute_values[lesson_map_placeholder] = {}
                    lessons_processed.add(comp.lessonId)

                # Then set the specific section completion time (only if not already completed)
                set_expressions.append(
                    f"completion.{lesson_placeholder}.{section_placeholder} = if_not_exists(completion.{lesson_placeholder}.{section_placeholder}, {timestamp_placeholder})"
                )

            final_update_expression = "SET " + ", ".join(set_expressions)

            _LOGGER.debug("DynamoDB UpdateItem for user_id %s:", user_id)
            _LOGGER.debug("  UpdateExpression: %s", final_update_expression)
            _LOGGER.debug("  ExpressionAttributeValues: %s", str(expression_attribute_values))
            _LOGGER.debug("  ExpressionAttributeNames: %s", str(expression_attribute_names))

            update_params = {
                "Key": {"userId": user_id},
                "UpdateExpression": final_update_expression,
                "ExpressionAttributeValues": expression_attribute_values,
                "ReturnValues": "ALL_NEW",
            }
            if expression_attribute_names:
                update_params["ExpressionAttributeNames"] = expression_attribute_names

            response = self.table.update_item(**update_params)
            updated_item = response.get("Attributes", {})

            if not updated_item:
                _LOGGER.error("UpdateItem did not return attributes for user_id: %s", user_id)
                return self.get_progress(user_id) or UserProgressModel(userId=user_id)

            return UserProgressModel.model_validate(updated_item)

        except ClientError as e:
            _LOGGER.exception(
                "Failed to update progress for user_id %s in DynamoDB: %s", user_id, e.response["Error"]["Message"]
            )
            raise
        except Exception as e_val:
            _LOGGER.exception("Failed to validate updated progress data for user_id %s: %s", user_id, str(e_val))
            raise
