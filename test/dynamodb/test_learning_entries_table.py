# test/dynamodb/test_learning_entries_table.py
import os
import typing
from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws

# Adjust the import path based on your project structure
from aws_src_sample.dynamodb.learning_entries_table import LearningEntriesTable
from aws_src_sample.models.learning_entry_models import (
    AssessmentLevel,
    ReflectionVersionItemModel,
)

REGION = "us-east-2"  # Consistent region for tests
TABLE_NAME = "test-learning-entry-versions-table"
GSI_NAME = "UserFinalLearningEntriesIndex"  # From LearningEntriesTable class


# Helper to create a sample item
def create_sample_item(
    user_id: str,
    lesson_id: str,
    section_id: str,
    *,
    timestamp_str: str = "2025-05-25",
    is_final: bool = False,
    ai_feedback: typing.Optional[str] = "Good work!",
    ai_assessment: typing.Optional[AssessmentLevel] = "achieves",
    source_version_id: typing.Optional[str] = None,
) -> ReflectionVersionItemModel:
    version_id = f"{lesson_id}#{section_id}#{timestamp_str}"
    item_data = {
        "versionId": version_id,
        "userId": user_id,
        "lessonId": lesson_id,
        "sectionId": section_id,
        "userTopic": f"Topic for {section_id}",
        "userCode": "print('hello')",
        "userExplanation": "This is an explanation.",
        "createdAt": timestamp_str,
        "isFinal": is_final,
        "aiFeedback": ai_feedback if not is_final else None,
        "aiAssessment": ai_assessment if not is_final else None,
        "sourceVersionId": source_version_id if is_final else None,
        "finalEntryCreatedAt": timestamp_str if is_final else None,
    }
    return ReflectionVersionItemModel(**item_data)


@pytest.fixture(scope="function")
def aws_credentials() -> typing.Iterator:
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = REGION
    yield
    del os.environ["AWS_ACCESS_KEY_ID"]
    del os.environ["AWS_SECRET_ACCESS_KEY"]
    del os.environ["AWS_SECURITY_TOKEN"]
    del os.environ["AWS_SESSION_TOKEN"]
    del os.environ["AWS_DEFAULT_REGION"]


@pytest.fixture
def dynamodb_table_object(aws_credentials) -> typing.Iterator:
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "userId", "KeyType": "HASH"},
                {"AttributeName": "versionId", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "userId", "AttributeType": "S"},
                {"AttributeName": "versionId", "AttributeType": "S"},
                {"AttributeName": "finalEntryCreatedAt", "AttributeType": "S"},  # For GSI SK
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": GSI_NAME,
                    "KeySchema": [
                        {"AttributeName": "userId", "KeyType": "HASH"},
                        {"AttributeName": "finalEntryCreatedAt", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield table


@pytest.fixture
def learning_entries_table_instance(dynamodb_table_object) -> LearningEntriesTable:
    """Create LearningEntriesTable instance."""
    return LearningEntriesTable(TABLE_NAME)


@mock_aws
def test_table_init(learning_entries_table_instance: LearningEntriesTable) -> None:
    """Test table initialization."""
    assert learning_entries_table_instance.table.table_name == TABLE_NAME
    assert learning_entries_table_instance.GSI_FINAL_ENTRIES_INDEX_NAME == GSI_NAME


@mock_aws
def test_save_and_get_version_by_id(learning_entries_table_instance: LearningEntriesTable) -> None:
    """Test saving a new item and retrieving it by versionId."""
    item1 = create_sample_item("user1", "lesson1", "sectionA", is_final=False)

    saved_item = learning_entries_table_instance.save_item(item1)
    assert saved_item == item1  # Save should return the input model

    retrieved_item = learning_entries_table_instance.get_version_by_id("user1", item1.versionId)
    assert retrieved_item is not None
    assert retrieved_item.model_dump() == item1.model_dump()


@mock_aws
def test_get_version_by_id_not_found(learning_entries_table_instance: LearningEntriesTable) -> None:
    """Test retrieving a non-existent item by versionId returns None."""
    retrieved_item = learning_entries_table_instance.get_version_by_id("user-nonexist", "lessonX#sectionY#timestampZ")
    assert retrieved_item is None


@mock_aws
def test_get_draft_versions_for_section_multiple_items_and_sorting(
    learning_entries_table_instance: LearningEntriesTable,
) -> None:
    """Test retrieving multiple drafts for a section, ensuring correct filtering and sorting (newest first)."""
    user_id = "user-drafts"
    lesson_id = "l1"
    section_id = "s1"

    draft1 = create_sample_item(
        user_id, lesson_id, section_id, timestamp_str="2025-05-24", is_final=False, ai_feedback="fb1"
    )
    draft2 = create_sample_item(
        user_id, lesson_id, section_id, timestamp_str="2025-05-25", is_final=False, ai_feedback="fb2"
    )
    draft3 = create_sample_item(
        user_id, lesson_id, section_id, timestamp_str="2025-05-26", is_final=False, ai_feedback="fb3"
    )
    # A final item in the same section for the same user (should be filtered out)
    final_item = create_sample_item(
        user_id, lesson_id, section_id, timestamp_str="2025-05-27", is_final=True, source_version_id=draft3.versionId
    )

    learning_entries_table_instance.save_item(draft1)
    learning_entries_table_instance.save_item(draft2)
    learning_entries_table_instance.save_item(draft3)
    learning_entries_table_instance.save_item(final_item)

    drafts, _ = learning_entries_table_instance.get_versions_for_section(
        user_id,
        lesson_id,
        section_id,
        filter_mode="drafts_only",
    )

    assert len(drafts) == 3
    assert drafts[0].versionId == draft3.versionId  # Newest first due to ScanIndexForward=False
    assert drafts[1].versionId == draft2.versionId
    assert drafts[2].versionId == draft1.versionId
    assert all(not d.isFinal for d in drafts)


@mock_aws
def test_get_draft_versions_for_section_empty(learning_entries_table_instance: LearningEntriesTable):
    """Test retrieving drafts when none exist for the section."""
    drafts, last_key = learning_entries_table_instance.get_versions_for_section(
        "user-empty-drafts",
        "l-empty",
        "s-empty",
        filter_mode="drafts_only",
    )
    assert len(drafts) == 0
    assert last_key is None


@mock_aws
def test_get_draft_versions_pagination(learning_entries_table_instance: LearningEntriesTable):
    """Test pagination for get_draft_versions_for_section."""
    user_id = "user-paginate-drafts"
    lesson_id = "l-page"
    section_id = "s-page"
    items_to_create = 5

    for i in range(items_to_create):
        item = create_sample_item(
            user_id, lesson_id, section_id, timestamp_str=f"2025-05-2{i}", is_final=False, ai_feedback=f"Feedback {i}"
        )
        learning_entries_table_instance.save_item(item)

    # Get first page (limit 2)
    page1_items, last_key1 = learning_entries_table_instance.get_versions_for_section(
        user_id,
        lesson_id,
        section_id,
        limit=2,
        filter_mode="drafts_only",
    )
    assert len(page1_items) == 2
    assert last_key1 is not None
    # Items are newest first: item 4 (minute=4), item 3 (minute=3)
    assert page1_items[0].aiFeedback == "Feedback 4"
    assert page1_items[1].aiFeedback == "Feedback 3"

    # Get second page
    page2_items, last_key2 = learning_entries_table_instance.get_versions_for_section(
        user_id,
        lesson_id,
        section_id,
        limit=2,
        last_evaluated_key=last_key1,
        filter_mode="drafts_only",
    )
    assert len(page2_items) == 2
    assert last_key2 is not None
    # Items: item 2 (minute=2), item 1 (minute=1)
    assert page2_items[0].aiFeedback == "Feedback 2"
    assert page2_items[1].aiFeedback == "Feedback 1"

    # Get third page (should have 1 item)
    page3_items, last_key3 = learning_entries_table_instance.get_versions_for_section(
        user_id,
        lesson_id,
        section_id,
        limit=2,
        last_evaluated_key=last_key2,
        filter_mode="drafts_only",
    )
    assert len(page3_items) == 1
    assert last_key3 is None  # No more items
    # Item: item 0 (minute=0)
    assert page3_items[0].aiFeedback == "Feedback 0"


@mock_aws
def test_get_most_recent_draft_for_section(learning_entries_table_instance: LearningEntriesTable) -> None:
    """Test retrieving the single most recent draft."""
    user_id = "user-recent-draft"
    lesson_id = "l-recent"
    section_id = "s-recent"

    old_draft = create_sample_item(
        user_id, lesson_id, section_id, timestamp_str="2025-05-24", is_final=False, ai_feedback="old"
    )
    new_draft = create_sample_item(
        user_id, lesson_id, section_id, timestamp_str="2025-05-25", is_final=False, ai_feedback="new"
    )
    # A final item that should be ignored by this method
    final_item = create_sample_item(
        user_id,
        lesson_id,
        section_id,
        timestamp_str="2025-05-26",
        is_final=True,
        source_version_id=new_draft.versionId,
    )

    learning_entries_table_instance.save_item(old_draft)
    learning_entries_table_instance.save_item(new_draft)
    learning_entries_table_instance.save_item(final_item)

    most_recent = learning_entries_table_instance.get_most_recent_draft_for_section(user_id, lesson_id, section_id)
    assert most_recent is not None
    assert most_recent.versionId == new_draft.versionId
    assert most_recent.aiFeedback == "new"


@mock_aws
def test_get_most_recent_draft_for_section_none_exist(learning_entries_table_instance: LearningEntriesTable):
    """Test get_most_recent_draft_for_section when no drafts exist."""
    most_recent = learning_entries_table_instance.get_most_recent_draft_for_section("user-no-recent", "lx", "sx")
    assert most_recent is None


@mock_aws
def test_get_finalized_entries_for_user(learning_entries_table_instance: LearningEntriesTable):
    """Test retrieving finalized entries using the GSI."""
    user_id1 = "user-final-1"
    user_id2 = "user-final-2"  # Different user

    # User 1 items
    draft_u1 = create_sample_item(user_id1, "l1", "s1", timestamp_str="2025-05-24", is_final=False)

    final_u1_item1 = create_sample_item(
        user_id1, "l1", "s1", timestamp_str="2025-05-25", is_final=True, source_version_id=draft_u1.versionId
    )

    final_u1_item2 = create_sample_item(
        user_id1, "l2", "s2", timestamp_str="2025-05-26", is_final=True, source_version_id="some-draft-id"
    )

    # User 2 item (should not appear for user1 query)
    final_u2_item1 = create_sample_item(
        user_id2, "l1", "s1", timestamp_str="2025-05-27", is_final=True, source_version_id="another-draft-id"
    )

    learning_entries_table_instance.save_item(draft_u1)
    learning_entries_table_instance.save_item(final_u1_item1)
    learning_entries_table_instance.save_item(final_u1_item2)
    learning_entries_table_instance.save_item(final_u2_item1)

    final_entries, _ = learning_entries_table_instance.get_finalized_entries_for_user(user_id1)
    assert len(final_entries) == 2
    # GSI query with ScanIndexForward=False should return newest first
    assert final_entries[0].versionId == final_u1_item2.versionId
    assert final_entries[1].versionId == final_u1_item1.versionId
    assert all(f.isFinal and f.userId == user_id1 for f in final_entries)
    # Check that final entries have null aiFeedback/Assessment as per model from previous step
    assert final_entries[0].aiFeedback is None
    assert final_entries[0].aiAssessment is None


@mock_aws
def test_get_finalized_entries_for_user_empty(learning_entries_table_instance: LearningEntriesTable):
    """Test retrieving finalized entries when none exist for the user."""
    # Save a draft to ensure table is not totally empty, but no final entries
    draft = create_sample_item("user-no-finals", "l", "s", is_final=False)
    learning_entries_table_instance.save_item(draft)

    final_entries, last_key = learning_entries_table_instance.get_finalized_entries_for_user("user-no-finals")
    assert len(final_entries) == 0
    assert last_key is None
