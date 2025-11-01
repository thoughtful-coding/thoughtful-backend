import logging
import typing

import boto3
import pydantic
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from thoughtful_backend.models.learning_entry_models import ReflectionVersionItemModel
from thoughtful_backend.utils.base_types import LessonId, SectionId, UserId

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class LearningEntriesTable:
    """
    A repository class to abstract DynamoDB operations for the LearningEntryVersionsTable,
    using Pydantic models for data validation and structure.
    """

    GSI_FINAL_ENTRIES_INDEX_NAME = "UserFinalLearningEntriesIndex"

    def __init__(self, table_name: str) -> None:
        self.client = boto3.resource("dynamodb")
        self.table = self.client.Table(table_name)
        logger.info(f"LearningEntryRepository initialized for table: {table_name}")

    def save_item(self, reflection_item: ReflectionVersionItemModel) -> ReflectionVersionItemModel:
        """
        Saves (creates or updates) a reflection item in the DynamoDB table.
        The item is validated against the Pydantic model before saving.

        :param reflection_item: A ReflectionVersionItemModel instance.
        :return: The saved ReflectionVersionItemModel instance.
        :raises: ValidationError if item_data is invalid, ClientError for DDB errors.
        """
        try:
            # Pydantic model ensures required fields are present if not optional.
            # model_dump (Pydantic V2) or dict (Pydantic V1) with exclude_none=True
            # ensures optional fields that are None are not written to DynamoDB,
            # which is good practice.
            item_dict = reflection_item.model_dump(exclude_none=True)

            self.table.put_item(Item=item_dict)
            logger.info(
                f"Successfully saved item with versionId: {reflection_item.versionId} for userId: {reflection_item.userId}"
            )
            return reflection_item
        except ClientError as e:
            logger.error(
                f"Error saving item (versionId: {reflection_item.versionId}) to DynamoDB: {e.response['Error']['Message']}",
                exc_info=True,
            )
            raise
        # ValidationError will be raised by Pydantic if reflection_item is not valid before calling this method,
        # or if parsing from a dict, that should happen before calling this method.

    def _parse_items(self, ddb_items: list[dict[str, typing.Any]]) -> list[ReflectionVersionItemModel]:
        """Helper to parse a list of DDB items into Pydantic models."""
        parsed_items = []
        for item in ddb_items:
            try:
                parsed_items.append(ReflectionVersionItemModel.model_validate(item))  # Pydantic v2
                # For Pydantic v1: ReflectionVersionItemModel.parse_obj(item)
            except pydantic.ValidationError as e:
                logger.error(f"Validation error for DDB item (versionId: {item.get('versionId')}): {e}", exc_info=True)
                # Decide how to handle: skip item, raise error, etc. For now, skipping.
        return parsed_items

    def get_versions_for_section(
        self,
        user_id: UserId,
        lesson_id: LessonId,
        section_id: SectionId,
        limit: int = 20,
        last_evaluated_key: typing.Optional[dict[str, typing.Any]] = None,
        filter_mode: typing.Literal["all", "drafts"] = "drafts",
    ) -> tuple[list[ReflectionVersionItemModel], typing.Optional[dict[str, typing.Any]]]:
        """
        Retrieves versions for a user, lesson, and section.
        - filter_mode 'drafts': Returns only items where isFinal is false. (Default)
        - filter_mode 'all': Returns all items for the section.
        """
        sk_prefix = f"{lesson_id}#{section_id}#"
        logger.info(f"Fetching versions for userId: {user_id}, SK prefix: {sk_prefix}, mode: {filter_mode}")

        query_kwargs: dict[str, typing.Any] = {
            "KeyConditionExpression": Key("userId").eq(user_id) & Key("versionId").begins_with(sk_prefix),
            "ScanIndexForward": False,  # Newest first
            "Limit": limit,
        }
        if last_evaluated_key:
            query_kwargs["ExclusiveStartKey"] = last_evaluated_key

        # Conditionally add the filter expression based on the new parameter
        if filter_mode == "drafts":
            query_kwargs["FilterExpression"] = Attr("isFinal").eq(False)

        try:
            response = self.table.query(**query_kwargs)
            ddb_items = response.get("Items", [])
            items = self._parse_items(ddb_items)
            new_last_evaluated_key = response.get("LastEvaluatedKey")
            logger.info(f"Found {len(items)} items with mode '{filter_mode}'. Has more: {bool(new_last_evaluated_key)}")
            return items, new_last_evaluated_key
        except ClientError as e:
            logger.error(
                f"Error fetching versions for userId: {user_id}, SK prefix: {sk_prefix}: {e.response['Error']['Message']}",
                exc_info=True,
            )
            raise

    def get_entries_for_user(
        self,
        user_id: UserId,
        filter_mode: typing.Literal["all", "final", "drafts"] = "all",
        limit: int = 50,
        last_evaluated_key: typing.Optional[dict[str, typing.Any]] = None,
    ) -> tuple[list[ReflectionVersionItemModel], typing.Optional[dict[str, typing.Any]]]:
        """
        Retrieves learning entries for a user with optional filtering.
        - filter_mode 'final': Returns only finalized entries (isFinal=true) using GSI
        - filter_mode 'drafts': Returns only draft entries (isFinal=false)
        - filter_mode 'all': Returns all entries (both drafts and final)

        Returns a list of Pydantic models and the pagination key.
        """
        logger.info(f"Fetching entries for userId: {user_id} with filter_mode: {filter_mode}")

        # For finalized entries, use the GSI for better performance
        if filter_mode == "final":
            query_kwargs: dict[str, typing.Any] = {
                "IndexName": self.GSI_FINAL_ENTRIES_INDEX_NAME,
                "KeyConditionExpression": Key("userId").eq(user_id),
                "ScanIndexForward": False,  # Newest first
                "Limit": limit,
            }
        else:
            # For 'all' or 'drafts', query the main table by userId
            query_kwargs: dict[str, typing.Any] = {
                "KeyConditionExpression": Key("userId").eq(user_id),
                "ScanIndexForward": False,  # Newest first
                "Limit": limit,
            }
            # Add filter expression for drafts mode
            if filter_mode == "drafts":
                query_kwargs["FilterExpression"] = Attr("isFinal").eq(False)

        if last_evaluated_key:
            query_kwargs["ExclusiveStartKey"] = last_evaluated_key

        try:
            response = self.table.query(**query_kwargs)
            ddb_items = response.get("Items", [])
            items = self._parse_items(ddb_items)
            new_last_evaluated_key = response.get("LastEvaluatedKey")
            logger.info(
                f"Found {len(items)} items with filter_mode '{filter_mode}'. Has more: {bool(new_last_evaluated_key)}"
            )
            return items, new_last_evaluated_key
        except ClientError as e:
            logger.error(
                f"Error fetching entries for userId: {user_id} with filter_mode '{filter_mode}': {e.response['Error']['Message']}",
                exc_info=True,
            )
            raise

    def get_version_by_id(self, user_id: UserId, version_id: str) -> typing.Optional[ReflectionVersionItemModel]:
        """
        Retrieves a single reflection version by its composite versionId (SK).
        Returns a Pydantic model instance or None if not found.
        """
        logger.info(f"Fetching version by ID: {version_id} for userId: {user_id}")
        try:
            response = self.table.get_item(Key={"userId": user_id, "versionId": version_id})  # This is the SK
            item_dict = response.get("Item")
            if item_dict:
                logger.info(f"Found item for versionId: {version_id}, parsing with Pydantic.")
                return ReflectionVersionItemModel.model_validate(item_dict)  # Pydantic V2
                # For Pydantic V1: ReflectionVersionItemModel.parse_obj(item_dict)
            else:
                logger.info(f"No item found for versionId: {version_id}")
                return None
        except pydantic.ValidationError as e:
            logger.error(f"Validation error for DDB item (versionId: {version_id}): {e}", exc_info=True)
            # Depending on desired behavior, you might return None or re-raise a custom error
            return None
        except ClientError as e:
            logger.error(
                f"Error fetching item by versionId: {version_id} for userId: {user_id}: {e.response['Error']['Message']}",
                exc_info=True,
            )
            raise

    def get_most_recent_draft_for_section(
        self,
        user_id: UserId,
        lesson_id: LessonId,
        section_id: SectionId,
    ) -> typing.Optional[ReflectionVersionItemModel]:
        """
        Retrieves the most recent draft version (isFinal=false) for a specific user, lesson, and section.
        """
        drafts, _ = self.get_versions_for_section(user_id, lesson_id, section_id, limit=2, filter_mode="drafts")
        if drafts:
            logger.info(f"Found most recent draft for {user_id} - {lesson_id}#{section_id}: {drafts[0].versionId}")
            return drafts[0]
        logger.info(f"No drafts found for {user_id} - {lesson_id}#{section_id}")
        return None
