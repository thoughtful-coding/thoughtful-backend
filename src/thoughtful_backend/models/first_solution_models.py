import typing

from pydantic import BaseModel, Field, field_validator

from thoughtful_backend.utils.base_types import IsoTimestamp, LessonId, SectionId, UnitId, UserId


class StoredFirstSolutionItemModel(BaseModel):
    """
    Represents a first solution as stored in DynamoDB.

    This model is used when returning first solutions to instructors for auditing.
    """

    sectionCompositeKey: str
    userId: UserId
    unitId: UnitId
    lessonId: LessonId
    sectionId: SectionId
    solution: str
    questionType: str
    submittedAt: IsoTimestamp

    @field_validator("solution")
    @classmethod
    def validate_solution_length(cls, v: str) -> str:
        """Validate that solution doesn't exceed 1000 characters."""
        if len(v) > 1000:
            raise ValueError("Solution exceeds maximum length of 1000 characters")
        return v

    class Config:
        populate_by_name = True


class FirstSolutionSubmissionResponseModel(BaseModel):
    """
    Response model for a list of first solution submissions.

    Used when instructors query all students' first solutions for a specific section.
    """

    submissions: list[StoredFirstSolutionItemModel]
    lastEvaluatedKey: typing.Optional[dict] = None

    class Config:
        populate_by_name = True
