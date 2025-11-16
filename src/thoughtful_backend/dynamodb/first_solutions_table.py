import logging
import typing
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from thoughtful_backend.utils.base_types import IsoTimestamp, LessonId, SectionId, UnitId, UserId

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class FirstSolutionsTable:
    """
    Data Abstraction Layer for storing students' first correct solutions.

    This table stores the first successful solution submitted by students for auditing purposes
    (e.g., detecting cheating). Solutions are write-once and limited to 1000 characters.

    Table Schema:
      - PK: sectionCompositeKey (String - e.g., "unitId#lessonId#sectionId")
      - SK: userId (String - student's ID)

    This schema optimizes for instructor queries: "Get all students' first solutions for a specific section"
    """

    MAX_SOLUTION_LENGTH = 1000

    def __init__(self, table_name: str):
        self.client = boto3.resource("dynamodb")
        self.table = self.client.Table(table_name)
        _LOGGER.info(f"FirstSolutionsTable initialized for table: {table_name}")

    def _make_section_composite_key(
        self,
        unit_id: UnitId,
        lesson_id: LessonId,
        section_id: SectionId,
    ) -> str:
        """Create composite key for the section (PK)."""
        return f"{unit_id}#{lesson_id}#{section_id}"

    def save_first_solution(
        self,
        user_id: UserId,
        unit_id: UnitId,
        lesson_id: LessonId,
        section_id: SectionId,
        solution: str,
        question_type: str = "testing",
        timestamp_iso: typing.Optional[IsoTimestamp] = None,
    ) -> bool:
        """
        Saves a student's first correct solution for a section.

        Args:
            user_id: Student's user ID
            unit_id: Unit identifier
            lesson_id: Lesson identifier
            section_id: Section identifier
            solution: The student's solution (max 1000 characters)
            question_type: Type of question (default: "testing", future: other types)
            timestamp_iso: Optional timestamp (defaults to now)

        Returns:
            True if saved successfully, False otherwise

        Raises:
            ValueError: If solution exceeds MAX_SOLUTION_LENGTH
        """
        if len(solution) > self.MAX_SOLUTION_LENGTH:
            raise ValueError(
                f"Solution exceeds maximum length of {self.MAX_SOLUTION_LENGTH} characters "
                f"(got {len(solution)} characters)"
            )

        if timestamp_iso is None:
            timestamp_iso = IsoTimestamp(datetime.now(timezone.utc).isoformat())

        section_key = self._make_section_composite_key(unit_id, lesson_id, section_id)

        item_to_save = {
            "sectionCompositeKey": section_key,
            "userId": user_id,
            "unitId": unit_id,
            "lessonId": lesson_id,
            "sectionId": section_id,
            "solution": solution,
            "questionType": question_type,
            "submittedAt": timestamp_iso,
        }

        try:
            # Use condition expression to ensure write-once behavior
            # This prevents overwriting if an item already exists
            self.table.put_item(
                Item=item_to_save,
                ConditionExpression="attribute_not_exists(sectionCompositeKey) AND attribute_not_exists(userId)",
            )
            _LOGGER.info(f"First solution saved for user '{user_id}' in section {unit_id}/{lesson_id}/{section_id}")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                _LOGGER.info(f"First solution already exists for user '{user_id}' in section {section_key}. Skipping.")
                return False
            else:
                _LOGGER.error(
                    f"Error saving first solution for user '{user_id}', section {section_key}: "
                    f"{e.response['Error']['Message']}"
                )
                return False

    def get_solutions_for_section(
        self,
        unit_id: UnitId,
        lesson_id: LessonId,
        section_id: SectionId,
        limit: typing.Optional[int] = None,
        last_evaluated_key: typing.Optional[dict] = None,
    ) -> typing.Tuple[list[dict], typing.Optional[dict]]:
        """
        Retrieves all students' first solutions for a specific section.

        This is primarily for instructor use to audit student submissions.

        Args:
            unit_id: Unit identifier
            lesson_id: Lesson identifier
            section_id: Section identifier
            limit: Maximum number of results to return
            last_evaluated_key: Pagination token from previous query

        Returns:
            Tuple of (list of solution items, next pagination token)
        """
        section_key = self._make_section_composite_key(unit_id, lesson_id, section_id)

        query_kwargs = {
            "KeyConditionExpression": Key("sectionCompositeKey").eq(section_key),
        }
        if limit:
            query_kwargs["Limit"] = limit
        if last_evaluated_key:
            query_kwargs["ExclusiveStartKey"] = last_evaluated_key

        solutions: list[dict] = []
        new_last_evaluated_key: typing.Optional[dict] = None

        try:
            response = self.table.query(**query_kwargs)
            solutions = response.get("Items", [])
            new_last_evaluated_key = response.get("LastEvaluatedKey")
            _LOGGER.info(f"Fetched {len(solutions)} first solutions for section {section_key}.")

        except ClientError as e:
            _LOGGER.error(f"Error fetching first solutions for section {section_key}: {e.response['Error']['Message']}")

        return solutions, new_last_evaluated_key

    def get_solution_for_student(
        self,
        user_id: UserId,
        unit_id: UnitId,
        lesson_id: LessonId,
        section_id: SectionId,
    ) -> typing.Optional[dict]:
        """
        Retrieves a specific student's first solution for a section.

        Args:
            user_id: Student's user ID
            unit_id: Unit identifier
            lesson_id: Lesson identifier
            section_id: Section identifier

        Returns:
            Solution item dict if found, None otherwise
        """
        section_key = self._make_section_composite_key(unit_id, lesson_id, section_id)

        try:
            response = self.table.get_item(
                Key={
                    "sectionCompositeKey": section_key,
                    "userId": user_id,
                }
            )
            item = response.get("Item")
            if item:
                _LOGGER.info(f"Retrieved first solution for user '{user_id}' in section {section_key}")
            else:
                _LOGGER.debug(f"No first solution found for user '{user_id}' in section {section_key}")
            return item

        except ClientError as e:
            _LOGGER.error(
                f"Error retrieving first solution for user '{user_id}', section {section_key}: "
                f"{e.response['Error']['Message']}"
            )
            return None
