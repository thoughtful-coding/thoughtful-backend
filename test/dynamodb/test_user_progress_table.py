import os
import typing
from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws

from thoughtful_backend.dynamodb.user_progress_table import UserProgressTable
from thoughtful_backend.models.user_progress_models import (
    SectionCompletionDetail,
    SectionCompletionInputModel,
    UserUnitProgressModel,
)
from thoughtful_backend.utils.base_types import (
    IsoTimestamp,
    LessonId,
    SectionId,
    UnitId,
    UserId,
)

REGION = "us-west-1"
TABLE_NAME = "UserProgressTable"


@pytest.fixture
def dynamodb_table_object(aws_credentials) -> typing.Iterator:
    """Creates the mock DynamoDB table using moto's context (via class decorator)."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "userId", "KeyType": "HASH"},  # Partition Key
                {"AttributeName": "unitId", "KeyType": "RANGE"},  # Sort Key
            ],
            AttributeDefinitions=[
                {"AttributeName": "userId", "AttributeType": "S"},
                {"AttributeName": "unitId", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield dynamodb  # Yield the resource, DAL will get table by name


@pytest.fixture
def progress_table_instance(dynamodb_table_object) -> UserProgressTable:
    """Create UserProgressTable instance. Relies on @mock_aws on the class."""
    return UserProgressTable(TABLE_NAME)


# Helper to create UserUnitProgressModel for putting items directly for setup
def _create_db_item_for_unit(
    user_id: UserId,
    unit_id: UnitId,
    completions: typing.Dict[LessonId, typing.Dict[SectionId, SectionCompletionDetail]],
) -> dict:
    model = UserUnitProgressModel(
        userId=user_id,
        unitId=unit_id,
        completion=completions,
    )
    return model.model_dump(by_alias=True, exclude_none=True)


def test_get_user_unit_progress_not_found(progress_table_instance: UserProgressTable):
    """Test getting progress for a non-existent user/unit combination."""
    result = progress_table_instance.get_user_unit_progress(UserId("non-existent-user"), UnitId("unit1"))
    assert result is None


def test_get_user_unit_progress_exists(progress_table_instance: UserProgressTable):
    """Test getting progress for an existing user/unit item."""
    user_id = UserId("student1")
    unit_id = UnitId("math_unit")
    lesson1_guid = LessonId("guid_lesson_math1")
    section1_id = SectionId("sec_intro")
    timestamp1 = IsoTimestamp(datetime.now(timezone.utc).isoformat())

    completion_detail = SectionCompletionDetail(completed_at=timestamp1, attempts_before_success=1)
    test_completions = {lesson1_guid: {section1_id: completion_detail}}
    db_item = _create_db_item_for_unit(user_id, unit_id, test_completions)

    # Use the DAL's table object to put the item for setup
    progress_table_instance.table.put_item(Item=db_item)

    result = progress_table_instance.get_user_unit_progress(user_id, unit_id)
    assert result is not None
    assert result.userId == user_id
    assert result.unitId == unit_id
    assert result.completion == test_completions


def test_get_all_unit_progress_no_items_for_user(progress_table_instance: UserProgressTable):
    result = progress_table_instance.get_all_unit_progress_for_user(UserId("user_no_units"))
    assert isinstance(result, list)
    assert len(result) == 0


def test_get_all_unit_progress_multiple_units(progress_table_instance: UserProgressTable):
    user_id = UserId("student_multi_unit")
    unit1_id = UnitId("unit_A")
    unit2_id = UnitId("unit_B")
    lessonA1_guid = LessonId("guid_lA1")
    lessonB1_guid = LessonId("guid_lB1")

    detail1 = SectionCompletionDetail(completed_at=IsoTimestamp("2025-01-01T00:00:00Z"), attempts_before_success=2)
    detail2 = SectionCompletionDetail(completed_at=IsoTimestamp("2025-01-02T00:00:00Z"), attempts_before_success=1)

    db_item1 = _create_db_item_for_unit(user_id, unit1_id, {lessonA1_guid: {"s1": detail1}})
    db_item2 = _create_db_item_for_unit(user_id, unit2_id, {lessonB1_guid: {"sX": detail2}})

    progress_table_instance.table.put_item(Item=db_item1)
    progress_table_instance.table.put_item(Item=db_item2)

    results = progress_table_instance.get_all_unit_progress_for_user(user_id)
    assert len(results) == 2

    unit_ids_found = {item.unitId for item in results}
    assert unit1_id in unit_ids_found
    assert unit2_id in unit_ids_found

    for item in results:
        if item.unitId == unit1_id:
            assert item.completion == {lessonA1_guid: {"s1": detail1}}
        elif item.unitId == unit2_id:
            assert item.completion == {lessonB1_guid: {"sX": detail2}}


# --- Tests for batch_update_user_progress ---


def test_batch_update_new_user_new_unit_new_lesson_new_section(progress_table_instance: UserProgressTable):
    user_id = UserId("new_user_progress")
    unit_id = UnitId("new_unit")
    lesson_guid = LessonId("new_lesson_guid")
    section_id = SectionId("new_section")

    completions_to_add = [
        SectionCompletionInputModel(unitId=unit_id, lessonId=lesson_guid, sectionId=section_id, attemptsBeforeSuccess=3)
    ]

    updated_units_map = progress_table_instance.batch_update_user_progress(user_id, completions_to_add)

    assert unit_id in updated_units_map
    updated_unit_progress = updated_units_map[unit_id]

    assert updated_unit_progress is not None
    assert updated_unit_progress.userId == user_id
    assert updated_unit_progress.unitId == unit_id
    assert lesson_guid in updated_unit_progress.completion
    assert section_id in updated_unit_progress.completion[lesson_guid]

    completion_detail = updated_unit_progress.completion[lesson_guid][section_id]
    assert isinstance(completion_detail, SectionCompletionDetail)
    assert completion_detail.attempts_before_success == 3
    assert completion_detail.completed_at is not None

    # Verify directly from DB
    db_check = progress_table_instance.get_user_unit_progress(user_id, unit_id)
    assert db_check is not None
    assert db_check.completion[lesson_guid][section_id] == updated_unit_progress.completion[lesson_guid][section_id]


def test_batch_update_existing_user_existing_unit_new_lesson(progress_table_instance: UserProgressTable):
    user_id = UserId("existing_user1")
    unit_id = UnitId("existing_unit1")
    lesson1_guid = LessonId("lesson1_guid")
    sectionA_id = SectionId("sectionA")
    lesson2_guid = LessonId("lesson2_guid")  # New lesson
    sectionB_id = SectionId("sectionB")

    # Pre-populate with lesson1 progress
    initial_detail = SectionCompletionDetail(
        completed_at=IsoTimestamp("2025-01-01T00:00:00Z"), attempts_before_success=1
    )
    initial_completions = {lesson1_guid: {sectionA_id: initial_detail}}
    initial_item = _create_db_item_for_unit(user_id, unit_id, initial_completions)
    progress_table_instance.table.put_item(Item=initial_item)

    completions_to_add = [
        SectionCompletionInputModel(
            unitId=unit_id, lessonId=lesson2_guid, sectionId=sectionB_id, attemptsBeforeSuccess=2
        )
    ]
    updated_units_map = progress_table_instance.batch_update_user_progress(user_id, completions_to_add)

    assert unit_id in updated_units_map
    updated_unit_progress = updated_units_map[unit_id]

    assert lesson1_guid in updated_unit_progress.completion  # Existing lesson still there
    assert sectionA_id in updated_unit_progress.completion[lesson1_guid]
    assert lesson2_guid in updated_unit_progress.completion  # New lesson added
    assert sectionB_id in updated_unit_progress.completion[lesson2_guid]


def test_batch_update_existing_user_existing_unit_existing_lesson_new_section(
    progress_table_instance: UserProgressTable,
):
    user_id = UserId("existing_user2")
    unit_id = UnitId("existing_unit2")
    lesson_guid = LessonId("lesson_guid_abc")
    section1_id = SectionId("section1")
    section2_id = SectionId("section2")  # New section for existing lesson

    initial_detail = SectionCompletionDetail(
        completed_at=IsoTimestamp("2025-01-01T00:00:00Z"), attempts_before_success=1
    )
    initial_completions = {lesson_guid: {section1_id: initial_detail}}
    initial_item = _create_db_item_for_unit(user_id, unit_id, initial_completions)
    progress_table_instance.table.put_item(Item=initial_item)

    completions_to_add = [
        SectionCompletionInputModel(
            unitId=unit_id, lessonId=lesson_guid, sectionId=section2_id, attemptsBeforeSuccess=4
        )
    ]
    updated_units_map = progress_table_instance.batch_update_user_progress(user_id, completions_to_add)

    assert unit_id in updated_units_map
    updated_unit_progress = updated_units_map[unit_id]

    assert section1_id in updated_unit_progress.completion[lesson_guid]
    assert section2_id in updated_unit_progress.completion[lesson_guid]  # New section added


def test_batch_update_section_already_completed_preserves_original_timestamp(
    progress_table_instance: UserProgressTable,
):
    user_id = UserId("user_preserve_ts")
    unit_id = UnitId("unit_ts")
    lesson_guid = LessonId("lesson_ts_guid")
    section_id = SectionId("section_ts")

    original_detail = SectionCompletionDetail(
        completed_at=IsoTimestamp("2025-01-01T00:00:00Z"), attempts_before_success=2
    )
    initial_completions = {lesson_guid: {section_id: original_detail}}
    initial_item = _create_db_item_for_unit(user_id, unit_id, initial_completions)
    progress_table_instance.table.put_item(Item=initial_item)

    completions_to_add = [  # Attempt to complete the same section again
        SectionCompletionInputModel(unitId=unit_id, lessonId=lesson_guid, sectionId=section_id, attemptsBeforeSuccess=5)
    ]
    updated_units_map = progress_table_instance.batch_update_user_progress(user_id, completions_to_add)

    assert unit_id in updated_units_map
    updated_unit_progress = updated_units_map[unit_id]

    # Detail should be the original one (not updated)
    assert updated_unit_progress.completion[lesson_guid][section_id] == original_detail


def test_batch_update_multiple_units_and_lessons(progress_table_instance: UserProgressTable):
    user_id = UserId("user_multi_all")
    unit1_id = UnitId("unitX")
    unit2_id = UnitId("unitY")
    lessonX1_guid = LessonId("LX1")
    lessonX2_guid = LessonId("LX2")
    lessonY1_guid = LessonId("LY1")

    completions_to_add = [
        SectionCompletionInputModel(
            unitId=unit1_id, lessonId=lessonX1_guid, sectionId=SectionId("sA"), attemptsBeforeSuccess=1
        ),
        SectionCompletionInputModel(
            unitId=unit1_id, lessonId=lessonX1_guid, sectionId=SectionId("sB"), attemptsBeforeSuccess=2
        ),
        SectionCompletionInputModel(
            unitId=unit1_id, lessonId=lessonX2_guid, sectionId=SectionId("sC"), attemptsBeforeSuccess=3
        ),
        SectionCompletionInputModel(
            unitId=unit2_id, lessonId=lessonY1_guid, sectionId=SectionId("sD"), attemptsBeforeSuccess=1
        ),
    ]
    updated_units_map = progress_table_instance.batch_update_user_progress(user_id, completions_to_add)

    assert len(updated_units_map) == 2
    assert unit1_id in updated_units_map
    assert unit2_id in updated_units_map

    progress_unitX = updated_units_map[unit1_id]
    assert len(progress_unitX.completion[lessonX1_guid]) == 2
    assert SectionId("sA") in progress_unitX.completion[lessonX1_guid]
    assert SectionId("sB") in progress_unitX.completion[lessonX1_guid]
    assert len(progress_unitX.completion[lessonX2_guid]) == 1
    assert SectionId("sC") in progress_unitX.completion[lessonX2_guid]

    progress_unitY = updated_units_map[unit2_id]
    assert len(progress_unitY.completion[lessonY1_guid]) == 1
    assert SectionId("sD") in progress_unitY.completion[lessonY1_guid]


def test_batch_update_empty_completions_list(progress_table_instance: UserProgressTable):
    user_id = UserId("user_empty_batch")
    # Ensure user might exist but with no progress for a unit
    progress_table_instance.table.put_item(Item={"userId": user_id, "unitId": UnitId("unit_exists_empty")})

    updated_units_map = progress_table_instance.batch_update_user_progress(user_id, [])
    assert len(updated_units_map) == 0  # No units should be modified or returned if no completions

    # If user didn't exist at all
    updated_units_map_new_user = progress_table_instance.batch_update_user_progress(UserId("new_user_empty_batch"), [])
    assert len(updated_units_map_new_user) == 0
