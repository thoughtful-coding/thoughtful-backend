import typing

from pydantic import BaseModel, Field

from aws_src_sample.models.learning_entry_models import AssessmentLevel
from aws_src_sample.utils.base_types import IsoTimestamp, LessonId, SectionId, UserId


class PrimmEvaluationRequestModel(BaseModel):
    lesson_id: LessonId = Field(..., alias="lessonId")
    section_id: SectionId = Field(..., alias="sectionId")
    primm_example_id: str = Field(..., alias="primmExampleId")
    code_snippet: str = Field(..., alias="codeSnippet")
    user_prediction_prompt_text: str = Field(..., alias="userPredictionPromptText")
    user_prediction_text: str = Field(..., alias="userPredictionText")
    user_prediction_confidence: int = Field(..., alias="userPredictionConfidence")
    user_explanation_text: str = Field(..., alias="userExplanationText")
    actual_output_summary: typing.Optional[str] = Field(None, alias="actualOutputSummary")

    class Config:
        populate_by_name = True  # Allows parsing JSON with camelCase keys to snake_case fields


class PrimmEvaluationResponseModel(BaseModel):
    ai_prediction_assessment: AssessmentLevel = Field(..., alias="aiPredictionAssessment")
    ai_explanation_assessment: AssessmentLevel = Field(..., alias="aiExplanationAssessment")
    ai_overall_comment: str = Field(..., alias="aiOverallComment")

    class Config:
        populate_by_name = True


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
    userPredictionConfidence: int  # Pydantic will handle Decimal -> int conversion
    actualOutputSummary: typing.Optional[str] = None
    userExplanationText: str

    # AI Evaluation fields from PrimmEvaluationResponseModel
    aiPredictionAssessment: AssessmentLevel
    aiExplanationAssessment: typing.Optional[AssessmentLevel] = None
    aiOverallComment: typing.Optional[str] = None

    class Config:
        populate_by_name = True
