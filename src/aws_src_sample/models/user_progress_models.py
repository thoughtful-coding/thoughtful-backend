from pydantic import BaseModel, Field


class SectionCompletionModel(BaseModel):
    lessonId: str
    sectionId: str


class BatchCompletionsInputModel(BaseModel):
    completions: list[SectionCompletionModel]


class UserProgressResponseModel(BaseModel):
    userId: str
    # completion structure: lessonId -> sectionId -> timeFirstCompleted
    completion: dict[str, dict[str, str]] = Field(default_factory=dict)
