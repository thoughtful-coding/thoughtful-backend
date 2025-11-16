import typing

import boto3
import pytest
from moto import mock_aws

from thoughtful_backend.dynamodb.first_solutions_table import FirstSolutionsTable
from thoughtful_backend.utils.base_types import LessonId, SectionId, UnitId, UserId

REGION = "us-west-1"
TABLE_NAME = "FirstSolutionsTable"


@pytest.fixture
def dynamodb_table_resource(aws_credentials) -> typing.Iterable:
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "sectionCompositeKey", "KeyType": "HASH"},  # PK
                {"AttributeName": "userId", "KeyType": "RANGE"},  # SK
            ],
            AttributeDefinitions=[
                {"AttributeName": "sectionCompositeKey", "AttributeType": "S"},
                {"AttributeName": "userId", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield dynamodb


@pytest.fixture
def first_solutions_table_instance(dynamodb_table_resource) -> FirstSolutionsTable:
    return FirstSolutionsTable(TABLE_NAME)


def test_save_first_solution_successful(first_solutions_table_instance: FirstSolutionsTable):
    user_id = UserId("student1")
    unit_id = UnitId("unit1")
    lesson_id = LessonId("lesson1")
    section_id = SectionId("section1")
    solution = "print('Hello, World!')"

    success = first_solutions_table_instance.save_first_solution(
        user_id=user_id,
        unit_id=unit_id,
        lesson_id=lesson_id,
        section_id=section_id,
        solution=solution,
    )
    assert success is True

    # Verify item in DynamoDB
    section_key = first_solutions_table_instance._make_section_composite_key(unit_id, lesson_id, section_id)
    response = first_solutions_table_instance.table.get_item(
        Key={"sectionCompositeKey": section_key, "userId": user_id}
    )
    item = response.get("Item")

    assert item is not None
    assert item["userId"] == user_id
    assert item["unitId"] == unit_id
    assert item["lessonId"] == lesson_id
    assert item["sectionId"] == section_id
    assert item["solution"] == solution
    assert item["questionType"] == "testing"
    assert "submittedAt" in item


def test_save_first_solution_exceeds_max_length(first_solutions_table_instance: FirstSolutionsTable):
    user_id = UserId("student2")
    unit_id = UnitId("unit1")
    lesson_id = LessonId("lesson1")
    section_id = SectionId("section1")
    solution = "x" * 1001  # Exceeds 1000 character limit

    with pytest.raises(ValueError, match="Solution exceeds maximum length"):
        first_solutions_table_instance.save_first_solution(
            user_id=user_id,
            unit_id=unit_id,
            lesson_id=lesson_id,
            section_id=section_id,
            solution=solution,
        )


def test_save_first_solution_write_once_behavior(first_solutions_table_instance: FirstSolutionsTable):
    user_id = UserId("student3")
    unit_id = UnitId("unit1")
    lesson_id = LessonId("lesson1")
    section_id = SectionId("section1")
    first_solution = "print('First attempt')"
    second_solution = "print('Second attempt')"

    # First save should succeed
    success1 = first_solutions_table_instance.save_first_solution(
        user_id=user_id,
        unit_id=unit_id,
        lesson_id=lesson_id,
        section_id=section_id,
        solution=first_solution,
    )
    assert success1 is True

    # Second save for same user/section should fail (write-once)
    success2 = first_solutions_table_instance.save_first_solution(
        user_id=user_id,
        unit_id=unit_id,
        lesson_id=lesson_id,
        section_id=section_id,
        solution=second_solution,
    )
    assert success2 is False

    # Verify original solution is still in DB
    section_key = first_solutions_table_instance._make_section_composite_key(unit_id, lesson_id, section_id)
    response = first_solutions_table_instance.table.get_item(
        Key={"sectionCompositeKey": section_key, "userId": user_id}
    )
    item = response.get("Item")
    assert item["solution"] == first_solution  # Original solution preserved


def test_get_solutions_for_section_multiple_students(first_solutions_table_instance: FirstSolutionsTable):
    unit_id = UnitId("unit1")
    lesson_id = LessonId("lesson1")
    section_id = SectionId("section1")

    # Save solutions from multiple students
    students_and_solutions = [
        (UserId("student1"), "print('Solution 1')"),
        (UserId("student2"), "print('Solution 2')"),
        (UserId("student3"), "print('Solution 3')"),
    ]

    for user_id, solution in students_and_solutions:
        first_solutions_table_instance.save_first_solution(
            user_id=user_id,
            unit_id=unit_id,
            lesson_id=lesson_id,
            section_id=section_id,
            solution=solution,
        )

    # Retrieve all solutions for the section
    solutions, last_key = first_solutions_table_instance.get_solutions_for_section(
        unit_id=unit_id,
        lesson_id=lesson_id,
        section_id=section_id,
    )

    assert len(solutions) == 3
    assert last_key is None

    # Verify all students are represented
    user_ids = {sol["userId"] for sol in solutions}
    assert user_ids == {"student1", "student2", "student3"}


def test_get_solutions_for_section_empty(first_solutions_table_instance: FirstSolutionsTable):
    solutions, last_key = first_solutions_table_instance.get_solutions_for_section(
        unit_id=UnitId("nonexistent-unit"),
        lesson_id=LessonId("nonexistent-lesson"),
        section_id=SectionId("nonexistent-section"),
    )

    assert len(solutions) == 0
    assert last_key is None


def test_get_solution_for_student_found(first_solutions_table_instance: FirstSolutionsTable):
    user_id = UserId("student4")
    unit_id = UnitId("unit1")
    lesson_id = LessonId("lesson1")
    section_id = SectionId("section1")
    solution = "print('Student 4 solution')"

    first_solutions_table_instance.save_first_solution(
        user_id=user_id,
        unit_id=unit_id,
        lesson_id=lesson_id,
        section_id=section_id,
        solution=solution,
    )

    retrieved = first_solutions_table_instance.get_solution_for_student(
        user_id=user_id,
        unit_id=unit_id,
        lesson_id=lesson_id,
        section_id=section_id,
    )

    assert retrieved is not None
    assert retrieved["userId"] == user_id
    assert retrieved["solution"] == solution


def test_get_solution_for_student_not_found(first_solutions_table_instance: FirstSolutionsTable):
    retrieved = first_solutions_table_instance.get_solution_for_student(
        user_id=UserId("nonexistent-student"),
        unit_id=UnitId("unit1"),
        lesson_id=LessonId("lesson1"),
        section_id=SectionId("section1"),
    )

    assert retrieved is None


def test_solutions_isolated_by_section(first_solutions_table_instance: FirstSolutionsTable):
    """Test that solutions for different sections don't interfere with each other."""
    user_id = UserId("student5")
    unit_id = UnitId("unit1")
    lesson_id = LessonId("lesson1")

    # Save solutions for two different sections
    first_solutions_table_instance.save_first_solution(
        user_id=user_id,
        unit_id=unit_id,
        lesson_id=lesson_id,
        section_id=SectionId("section1"),
        solution="Solution for section 1",
    )

    first_solutions_table_instance.save_first_solution(
        user_id=user_id,
        unit_id=unit_id,
        lesson_id=lesson_id,
        section_id=SectionId("section2"),
        solution="Solution for section 2",
    )

    # Retrieve solutions for section1 only
    solutions_s1, _ = first_solutions_table_instance.get_solutions_for_section(
        unit_id=unit_id,
        lesson_id=lesson_id,
        section_id=SectionId("section1"),
    )

    assert len(solutions_s1) == 1
    assert solutions_s1[0]["solution"] == "Solution for section 1"

    # Retrieve solutions for section2 only
    solutions_s2, _ = first_solutions_table_instance.get_solutions_for_section(
        unit_id=unit_id,
        lesson_id=lesson_id,
        section_id=SectionId("section2"),
    )

    assert len(solutions_s2) == 1
    assert solutions_s2[0]["solution"] == "Solution for section 2"
