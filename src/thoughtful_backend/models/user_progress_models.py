from pydantic import BaseModel, Field

from thoughtful_backend.utils.base_types import (
    IsoTimestamp,
    LessonId,
    SectionId,
    UnitId,
    UserId,
)


class SectionCompletionInputModel(BaseModel):
    unitId: UnitId
    lessonId: LessonId
    sectionId: SectionId


class BatchCompletionsInputModel(BaseModel):
    completions: list[SectionCompletionInputModel]


class UserUnitProgressModel(BaseModel):
    userId: UserId
    unitId: UnitId
    # completion structure: lessonId -> sectionId -> timeFirstCompleted
    completion: dict[LessonId, dict[SectionId, IsoTimestamp]] = Field(default_factory=dict)


class UserProgressModel(BaseModel):
    userId: UserId
    completion: dict[UnitId, dict[LessonId, dict[SectionId, IsoTimestamp]]] = Field(default_factory=dict)
