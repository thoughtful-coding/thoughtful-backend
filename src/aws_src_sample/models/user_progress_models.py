from pydantic import BaseModel, Field


class SectionCompletionInputModel(BaseModel):
    lessonId: str
    sectionId: str


class BatchCompletionsInputModel(BaseModel):
    completions: list[SectionCompletionInputModel]


class UserProgressModel(BaseModel):
    userId: str
    # completion structure: lessonId -> sectionId -> timeFirstCompleted
    completion: dict[str, dict[str, str]] = Field(default_factory=dict)
