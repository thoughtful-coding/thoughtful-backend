from pydantic import BaseModel, Field

from aws_src_sample.utils.base_types import IsoTimestamp, LessonId, SectionId, UserId


class SectionCompletionInputModel(BaseModel):
    lessonId: LessonId
    sectionId: SectionId


class BatchCompletionsInputModel(BaseModel):
    completions: list[SectionCompletionInputModel]


class UserProgressModel(BaseModel):
    userId: UserId
    # completion structure: lessonId -> sectionId -> timeFirstCompleted
    completion: dict[LessonId, dict[SectionId, IsoTimestamp]] = Field(default_factory=dict)
