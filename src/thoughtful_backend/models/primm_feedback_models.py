import typing

from pydantic import BaseModel

from thoughtful_backend.models.learning_entry_models import AssessmentLevel
from thoughtful_backend.utils.base_types import IsoTimestamp, LessonId, SectionId, UserId


class PrimmEvaluationRequestModel(BaseModel):
    lessonId: LessonId
    sectionId: SectionId
    primmExampleId: str
    codeSnippet: str
    userPredictionPromptText: str
    userPredictionText: str
    userExplanationText: str
    actualOutputSummary: typing.Optional[str] = None


class PrimmEvaluationResponseModel(BaseModel):
    aiPredictionAssessment: AssessmentLevel
    aiExplanationAssessment: AssessmentLevel
    aiOverallComment: str


class StoredPrimmSubmissionItemModel(BaseModel):
    # This model represents the full item as stored in DynamoDB
    userId: UserId
    submissionCompositeKey: str
    lessonId: LessonId
    sectionId: SectionId
    primmExampleId: str
    timestampIso: IsoTimestamp
    createdAt: IsoTimestamp

    # User Input fields from PrimmEvaluationRequestModel
    codeSnippet: str
    userPredictionPromptText: str
    userPredictionText: str
    actualOutputSummary: typing.Optional[str] = None
    userExplanationText: str

    # AI Evaluation fields from PrimmEvaluationResponseModel
    aiPredictionAssessment: AssessmentLevel
    aiExplanationAssessment: typing.Optional[AssessmentLevel] = None
    aiOverallComment: typing.Optional[str] = None
