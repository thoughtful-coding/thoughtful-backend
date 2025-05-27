import typing

from pydantic import BaseModel, Field

from aws_src_sample.models.learning_entry_models import AssessmentLevel


class PrimmEvaluationRequestModel(BaseModel):
    lesson_id: str = Field(..., alias="lessonId")
    section_id: str = Field(..., alias="sectionId")
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
