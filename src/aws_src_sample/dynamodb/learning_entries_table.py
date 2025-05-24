# src/aws_src_sample/dynamodb/learning_entries_table.py
import logging
import typing
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError
from pydantic import BaseModel

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


# --- Pydantic Model Definitions ---
class LearningEntrySubmissionModel(BaseModel):  # For validating incoming POST request body
    submissionTopic: str
    submissionCode: str
    submissionExplanation: str
    aiFeedback: str
    aiAssessment: typing.Literal["achieves", "mostly", "developing", "insufficient"]
    createdAt: str  # ISO 8601 string


class LearningEntryModel(BaseModel):
    userId: str
    entryId: str
    submissionTopic: str
    submissionCode: str
    submissionExplanation: str
    aiFeedback: str
    aiAssessment: typing.Literal["achieves", "mostly", "developing", "insufficient"]
    createdAt: str  # ISO 8601 string


class LearningEntriesTable:
    def __init__(self, table_name: str) -> None:
        self.client = boto3.resource("dynamodb")
        self.table = self.client.Table(table_name)

    def add_entry(self, user_id: str, payload: LearningEntrySubmissionModel) -> LearningEntryModel:
        """
        Adds a new learning entry to the DynamoDB table.
        :param user_id: The ID of the user submitting the entry.
        :param payload: The validated learning entry data.
        :return: The created LearningEntryModel.
        """
        _LOGGER.info("Attempting to add learning entry for user_id: %s", user_id)

        entry_id = str(uuid.uuid4())
        current_timestamp_iso = datetime.now(timezone.utc).isoformat()

        # Construct the full entry using Pydantic model for clarity and future validation
        entry_data = LearningEntryModel(
            userId=user_id,
            entryId=entry_id,
            submissionTopic=payload.submissionTopic,
            submissionCode=payload.submissionCode,
            submissionExplanation=payload.submissionExplanation,
            aiFeedback=payload.aiFeedback,
            aiAssessment=payload.aiAssessment,
            createdAt=current_timestamp_iso,
        )

        try:
            # Use model_dump() to get a dictionary suitable for DynamoDB
            # exclude_none=True can be useful if you have many optional fields
            # and don't want to store nulls, though DDB handles missing attributes.
            self.table.put_item(Item=entry_data.model_dump())
            _LOGGER.info("Successfully added entry with entryId: %s for user_id: %s", entry_id, user_id)
            return entry_data
        except ClientError as e:
            _LOGGER.exception(
                "Failed to add entry to DynamoDB for user_id: %s. Error: %s",
                user_id,
                e.response.get("Error", {}).get("Message"),
            )
            raise

    def get_entries_by_user(
        self,
        user_id: str,
        lesson_id_filter: typing.Optional[str] = None,
        section_id_filter: typing.Optional[str] = None,
    ) -> list[LearningEntryModel]:
        """
        Retrieves learning entries for a given user, with optional filters.
        Returns a list of Pydantic LearningEntryModel instances.
        """
        _LOGGER.info(
            "Fetching learning entries for user_id: %s with filters lesson_id=%s, section_id=%s",
            user_id,
            lesson_id_filter,
            section_id_filter,
        )
        try:
            key_condition_expression = Key("userId").eq(user_id)
            filter_expressions: list[typing.Any] = []

            query_kwargs: dict[str, typing.Any] = {"KeyConditionExpression": key_condition_expression}

            if lesson_id_filter:
                filter_expressions.append(Attr("lessonId").eq(lesson_id_filter))
            if section_id_filter:
                filter_expressions.append(Attr("sectionId").eq(section_id_filter))

            if filter_expressions:
                final_filter_expression = filter_expressions[0]
                for i in range(1, len(filter_expressions)):
                    final_filter_expression = final_filter_expression & filter_expressions[i]
                query_kwargs["FilterExpression"] = final_filter_expression

            response = self.table.query(**query_kwargs)
            db_items: list[dict[str, typing.Any]] = response.get("Items", [])

            # Handle pagination
            while "LastEvaluatedKey" in response:
                _LOGGER.info("Paginating for more entries for user_id: %s", user_id)
                query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                response = self.table.query(**query_kwargs)
                db_items.extend(response.get("Items", []))

            # Parse DynamoDB items into Pydantic models
            parsed_entries: list[LearningEntryModel] = []
            for item in db_items:
                try:
                    parsed_entries.append(LearningEntryModel.model_validate(item))
                except Exception as e_parse:  # Pydantic's ValidationError
                    _LOGGER.error(
                        "Failed to parse DynamoDB item into LearningEntryModel: %s. Item: %s", str(e_parse), item
                    )
                    # Decide how to handle parse errors: skip item, raise error, etc.
                    # For now, skipping problematic items.

            _LOGGER.info("Found and parsed %d entries for user_id: %s", len(parsed_entries), user_id)
            return parsed_entries
        except ClientError as e:
            _LOGGER.exception(
                "Failed to get entries from DynamoDB for user_id: %s. Error: %s",
                user_id,
                e.response.get("Error", {}).get("Message"),
            )
            raise
