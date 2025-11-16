# src/aws_src_sample/dynamodb/primm_submissions_dal.py
import logging
import typing
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# Assuming your Pydantic models are in primm_feedback_models as per your lambda
from thoughtful_backend.models.primm_feedback_models import (
    PrimmEvaluationRequestModel,
    PrimmEvaluationResponseModel,
    StoredPrimmSubmissionItemModel,
)
from thoughtful_backend.utils.base_types import IsoTimestamp, LessonId, SectionId, UserId

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class PrimmSubmissionsTable:
    """
    Data Abstraction Layer for interacting with the UserPrimmSubmissions DynamoDB table.
    Table Schema (as assumed from CDK implementation):
      - PK: userId (String - student's ID)
      - SK: submissionCompositeKey (String - e.g., lessonId#sectionId#primmExampleId#timestampIso)
    """

    def __init__(self, table_name: str):
        self.client = boto3.resource("dynamodb")
        self.table = self.client.Table(table_name)
        _LOGGER.info(f"PrimmSubmissionsTableDal initialized for table: {table_name}")

    def _make_submission_sk(
        self,
        lesson_id: LessonId,
        section_id: SectionId,
        primm_example_id: str,
        timestamp_iso: IsoTimestamp,
    ) -> str:
        return f"{lesson_id}#{section_id}#{primm_example_id}#{timestamp_iso}"

    def save_submission(
        self,
        user_id: UserId,
        request_data: PrimmEvaluationRequestModel,
        evaluation_data: PrimmEvaluationResponseModel,
        timestamp_iso: typing.Optional[IsoTimestamp] = None,
    ) -> bool:
        """
        Saves a PRIMM submission including the user's input and AI evaluation.
        """
        if timestamp_iso is None:
            timestamp_iso = IsoTimestamp(datetime.now(timezone.utc).isoformat())

        submission_sk = self._make_submission_sk(
            request_data.lesson_id, request_data.section_id, request_data.primm_example_id, timestamp_iso
        )

        item_to_save = {
            "userId": user_id,
            "submissionCompositeKey": submission_sk,
            "lessonId": request_data.lesson_id,
            "sectionId": request_data.section_id,
            "primmExampleId": request_data.primm_example_id,
            "timestampIso": timestamp_iso,  # Store the timestamp for querying/sorting if needed
            "createdAt": datetime.now(timezone.utc).isoformat(),  # General record creation time
            # From PrimmEvaluationRequestModel (user's input)
            "codeSnippet": request_data.code_snippet,
            "userPredictionPromptText": request_data.user_prediction_prompt_text,
            "userPredictionText": request_data.user_prediction_text,
            "actualOutputSummary": request_data.actual_output_summary,
            "userExplanationText": request_data.user_explanation_text,
            # From PrimmEvaluationResponseModel (AI's evaluation)
            # These align with your corrected Swagger for PrimmEvaluationResponse
            "aiPredictionAssessment": (
                evaluation_data.ai_prediction_assessment if evaluation_data.ai_prediction_assessment else None
            ),
            "aiExplanationAssessment": (
                evaluation_data.ai_explanation_assessment if evaluation_data.ai_explanation_assessment else None
            ),
            "aiOverallComment": evaluation_data.ai_overall_comment,
            # If you decide to store granular AI text feedback:
            # 'aiPredictionFeedback': evaluation_data.prediction_feedback,
            # 'aiExplanationFeedback': evaluation_data.explanation_feedback,
        }
        # Filter out None values from optional fields to not store them as null in DynamoDB
        item_to_save_cleaned = {k: v for k, v in item_to_save.items() if v is not None}

        try:
            self.table.put_item(Item=item_to_save_cleaned)
            _LOGGER.info(
                f"PRIMM submission saved for user '{user_id}', example '{request_data.primm_example_id}' at {timestamp_iso}."
            )
            return True
        except ClientError as e:
            _LOGGER.error(
                f"Error saving PRIMM submission for user '{user_id}', example '{request_data.primm_example_id}': {e.response['Error']['Message']}"
            )
            return False

    def get_submissions_by_student(
        self,
        user_id: UserId,
        lesson_id_filter: typing.Optional[str] = None,
        section_id_filter: typing.Optional[str] = None,
        primm_example_id_filter: typing.Optional[str] = None,
        limit: typing.Optional[int] = None,
        last_evaluated_key: typing.Optional[dict] = None,
    ) -> typing.Tuple[list[StoredPrimmSubmissionItemModel], typing.Optional[dict]]:  # Changed return type hint
        """
        Retrieves PRIMM submissions for a student, with optional filtering.
        Returns a list of submission items (as Pydantic models) and the LastEvaluatedKey for pagination.
        """
        key_condition_expression = Key("userId").eq(user_id)

        sk_prefix_parts = []
        if lesson_id_filter:
            sk_prefix_parts.append(lesson_id_filter)
            if section_id_filter:
                sk_prefix_parts.append(section_id_filter)
                if primm_example_id_filter:
                    sk_prefix_parts.append(primm_example_id_filter)

        if sk_prefix_parts:
            sk_prefix = "#".join(sk_prefix_parts) + "#"
            key_condition_expression = key_condition_expression & Key("submissionCompositeKey").begins_with(sk_prefix)

        query_kwargs = {
            "KeyConditionExpression": key_condition_expression,
            "ScanIndexForward": False,
        }
        if limit:
            query_kwargs["Limit"] = limit
        if last_evaluated_key:
            query_kwargs["ExclusiveStartKey"] = last_evaluated_key

        submissions: list[StoredPrimmSubmissionItemModel] = []  # Changed type hint
        new_last_evaluated_key: typing.Optional[dict] = None

        try:
            response = self.table.query(**query_kwargs)
            # This is the key change: Parse each item with the Pydantic model
            for item in response.get("Items", []):
                submissions.append(StoredPrimmSubmissionItemModel.model_validate(item))

            new_last_evaluated_key = response.get("LastEvaluatedKey")
            _LOGGER.info(f"Fetched and parsed {len(submissions)} PRIMM submissions for user '{user_id}'.")

        except ClientError as e:
            _LOGGER.error(f"Error fetching PRIMM submissions for user '{user_id}': {e.response['Error']['Message']}")
            # Return empty list and no key on error, or re-raise

        return submissions, new_last_evaluated_key
