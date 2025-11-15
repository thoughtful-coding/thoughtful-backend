from pydantic import BaseModel, Field

from thoughtful_backend.utils.base_types import (
    IsoTimestamp,
    LessonId,
    SectionId,
    UnitId,
    UserId,
)


class SectionCompletionDetail(BaseModel):
    """Details about a section completion, including timestamp and attempt count."""

    completed_at: IsoTimestamp = Field(..., alias="completedAt")
    attempts_before_success: int = Field(..., alias="attemptsBeforeSuccess", ge=1)

    class Config:
        populate_by_name = True


class SectionCompletionInputModel(BaseModel):
    unitId: UnitId
    lessonId: LessonId
    sectionId: SectionId
    attemptsBeforeSuccess: int = Field(..., ge=1)


class BatchCompletionsInputModel(BaseModel):
    completions: list[SectionCompletionInputModel]


class UserUnitProgressModel(BaseModel):
    userId: UserId
    unitId: UnitId
    # completion structure: lessonId -> sectionId -> SectionCompletionDetail
    completion: dict[LessonId, dict[SectionId, SectionCompletionDetail]] = Field(default_factory=dict)


class UserProgressModel(BaseModel):
    userId: UserId
    completion: dict[UnitId, dict[LessonId, dict[SectionId, SectionCompletionDetail]]] = Field(default_factory=dict)
