import logging
import typing
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field, field_validator

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


# --- Pydantic Model Definitions ---
class SectionCompletionModel(BaseModel):
    lessonId: str
    sectionId: str


class BatchCompletionsInputModel(BaseModel):  # Corresponds to Swagger
    completions: list[SectionCompletionModel]


class UserProgressModel(BaseModel):  # Corresponds to Swagger UserProgressState
    userId: str
    completion: dict[str, list[str]] = Field(default_factory=dict)  # lessonId -> list of sectionIds
    penaltyEndTime: typing.Optional[int] = None  # Unix timestamp in ms
    lastModifiedServerTimestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @field_validator("completion", mode="before")
    @classmethod
    def convert_dynamodb_sets_to_lists(cls, v: typing.Any) -> typing.Any:
        """Converts DynamoDB Set objects to Python lists if coming from DDB."""
        if isinstance(v, dict):
            return {key: list(value) if isinstance(value, set) else value for key, value in v.items()}
        return v


# --- End Pydantic Model Definitions ---


class UserProgressTable:
    """
    A wrapper class to abstract DynamoDB operations for the UserProgressTable.
    """

    def __init__(self, table_name: str) -> None:
        self.client = boto3.resource("dynamodb")
        self.table = self.client.Table(table_name)
        _LOGGER.info("Initialized UserProgressTable wrapper for table: %s", table_name)

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
                # Pydantic will handle conversion of DDB sets in completion map via validator
                return UserProgressModel.model_validate(item)
            _LOGGER.info("No progress found for user_id: %s", user_id)
            return None
        except ClientError as e:
            _LOGGER.exception(
                "Failed to get progress for user_id %s from DynamoDB: %s", user_id, e.response["Error"]["Message"]
            )
            raise
        except Exception as e_val:  # Catch Pydantic validation errors too
            _LOGGER.exception("Failed to validate progress data for user_id %s from DynamoDB: %s", user_id, str(e_val))
            # Potentially return None or re-raise depending on how strict you want to be with existing data
            return None

    def update_progress(self, user_id: str, completions_to_add: list[SectionCompletionModel]) -> UserProgressModel:
        """
        Updates user's progress by adding new section completions.
        This operation is additive (union) for completed sections.
        :param user_id: The ID of the user.
        :param completions_to_add: A list of SectionCompletionModel objects.
        :return: The updated UserProgressModel.
        """
        _LOGGER.info("Updating progress for user_id: %s with %d new completions.", user_id, len(completions_to_add))

        current_timestamp_iso = datetime.now(timezone.utc).isoformat()

        if not completions_to_add:  # Only update timestamp if no new completions
            try:
                response = self.table.update_item(
                    Key={"userId": user_id},
                    UpdateExpression="SET lastModifiedServerTimestamp = :ts",
                    ExpressionAttributeValues={":ts": current_timestamp_iso},
                    ReturnValues="ALL_NEW",
                )
                updated_item = response.get("Attributes", {})
                if updated_item:
                    return UserProgressModel.model_validate(updated_item)
                # If item didn't exist, create a minimal one
                new_progress = UserProgressModel(userId=user_id, lastModifiedServerTimestamp=current_timestamp_iso)
                self.table.put_item(Item=new_progress.model_dump())
                return new_progress
            except ClientError as e:
                _LOGGER.exception(
                    "Failed to update timestamp for user_id %s: %s", user_id, e.response["Error"]["Message"]
                )
                raise

        # Group completions by lessonId for efficient batching of ADD operations
        updates_by_lesson: dict[str, set[str]] = {}
        for comp in completions_to_add:
            if comp.lessonId not in updates_by_lesson:
                updates_by_lesson[comp.lessonId] = set()
            updates_by_lesson[comp.lessonId].add(comp.sectionId)

        # Build UpdateExpression and ExpressionAttributeValues/Names
        update_expressions: list[str] = ["SET lastModifiedServerTimestamp = :ts"]
        expression_attribute_values: dict[str, typing.Any] = {":ts": current_timestamp_iso}
        expression_attribute_names: dict[str, str] = {}

        # Ensure 'completion' map exists or is initialized
        # This is important if the user item is new or 'completion' map is not yet created.
        update_expressions.append("completion = if_not_exists(completion, :empty_map)")
        expression_attribute_values[":empty_map"] = {}

        for i, (lesson_id, section_ids_set) in enumerate(updates_by_lesson.items()):
            lesson_id_placeholder_name = f"#lesson{i}"
            section_ids_val_placeholder = f":sections{i}"

            # For DDB path: completion.lesson_id_with_slashes needs attribute name placeholder
            # because '/' is not allowed in unescaped attribute names.
            # Example: if lessonId is "00_intro/lesson_1", DDB path is completion.#LID0
            # where #LID0 = "00_intro/lesson_1"
            expression_attribute_names[lesson_id_placeholder_name] = lesson_id

            # Using ADD action for String Sets
            # Initialize the lesson's set if it doesn't exist, then add to it
            update_expressions.append(f"ADD completion.{lesson_id_placeholder_name} {section_ids_val_placeholder}")
            expression_attribute_values[section_ids_val_placeholder] = section_ids_set

        final_update_expression = ", ".join(update_expressions)

        _LOGGER.debug("DynamoDB UpdateItem for user_id %s:", user_id)
        _LOGGER.debug("  UpdateExpression: %s", final_update_expression)
        _LOGGER.debug("  ExpressionAttributeValues: %s", str(expression_attribute_values))
        if expression_attribute_names:
            _LOGGER.debug("  ExpressionAttributeNames: %s", str(expression_attribute_names))

        try:
            update_params: dict[str, typing.Any] = {
                "Key": {"userId": user_id},
                "UpdateExpression": final_update_expression,
                "ExpressionAttributeValues": expression_attribute_values,
                "ReturnValues": "ALL_NEW",
            }
            if expression_attribute_names:
                update_params["ExpressionAttributeNames"] = expression_attribute_names

            response = self.table.update_item(**update_params)
            updated_item = response.get("Attributes", {})
            if not updated_item:  # Should not happen with ReturnValues="ALL_NEW" unless item was deleted concurrently
                _LOGGER.error("UpdateItem did not return attributes for user_id: %s", user_id)
                # Fallback: fetch the item or construct a default
                return self.get_progress(user_id) or UserProgressModel(
                    userId=user_id,
                    completion={},
                    penaltyEndTime=None,
                    lastModifiedServerTimestamp=current_timestamp_iso,
                )

            return UserProgressModel.model_validate(updated_item)
        except ClientError as e:
            _LOGGER.exception(
                "Failed to update progress for user_id %s in DynamoDB: %s", user_id, e.response["Error"]["Message"]
            )
            raise
        except Exception as e_val:  # Pydantic validation errors
            _LOGGER.exception("Failed to validate updated progress data for user_id %s: %s", user_id, str(e_val))
            raise
