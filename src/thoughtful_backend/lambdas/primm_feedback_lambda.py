import json
import logging
import typing

from pydantic import ValidationError

from thoughtful_backend.cloudwatch.metrics import MetricsManager
from thoughtful_backend.dynamodb.primm_submissions_table import PrimmSubmissionsTable
from thoughtful_backend.dynamodb.throttle_table import (
    ThrottleRateLimitExceededException,
    ThrottleTable,
)
from thoughtful_backend.models.primm_feedback_models import (
    PrimmEvaluationRequestModel,
    PrimmEvaluationResponseModel,
)
from thoughtful_backend.secrets_manager.secrets_repository import SecretsRepository
from thoughtful_backend.utils.apig_utils import (
    ErrorCode,
    create_error_response,
    format_lambda_response,
    get_method,
    get_path,
    get_user_id_from_event,
)
from thoughtful_backend.utils.aws_env_vars import (
    get_primm_submissions_table_name,
    get_throttle_table_name,
)
from thoughtful_backend.utils.base_types import UserId
from thoughtful_backend.utils.chatbot_utils import ChatBotApiError, ChatBotWrapper

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class PrimmFeedbackApiHandler:
    def __init__(
        self,
        throttle_table: ThrottleTable,
        secrets_repo: SecretsRepository,
        chatbot_wrapper: ChatBotWrapper,
        primm_submissions_table: PrimmSubmissionsTable,
        metrics_manager: MetricsManager,
    ):
        self.throttle_table = throttle_table
        self.secrets_repo = secrets_repo
        self.chatbot_wrapper = chatbot_wrapper
        self.primm_submissions_table = primm_submissions_table
        self.metrics_manager = metrics_manager

    def _handle_post_request(self, event: dict, user_id: UserId) -> dict:
        _LOGGER.info(f"Processing PRIMM feedback request for user_id: {user_id}")

        try:
            raw_body = event.get("body")
            if not raw_body:
                _LOGGER.error("Request body is missing for PRIMM feedback.")
                return create_error_response(ErrorCode.VALIDATION_ERROR, "Request body is missing.", event=event)

            # Validate request body using Pydantic model
            request_data = PrimmEvaluationRequestModel.model_validate_json(raw_body)
            _LOGGER.info(
                f"Parsed PrimmEvaluationRequest for lesson: {request_data.lesson_id}, section: {request_data.section_id}, example: {request_data.primm_example_id}"
            )

        except ValidationError as e:
            _LOGGER.error(f"PRIMM feedback request body validation error: {e.errors()}", exc_info=True)
            return create_error_response(ErrorCode.VALIDATION_ERROR, details=e.errors(), event=event)
        except json.JSONDecodeError:
            _LOGGER.error("PRIMM feedback request body is not valid JSON.", exc_info=True)
            return create_error_response(ErrorCode.VALIDATION_ERROR, event=event)

        with self.throttle_table.throttle_action(user_id, "PRIMM_FEEDBACK_CHATBOT_API_CALL"):
            _LOGGER.info(f"Throttling check passed for user {user_id}. Calling ChatBot.")

            ai_eval_response: PrimmEvaluationResponseModel = self.chatbot_wrapper.call_primm_evaluation_api(
                chatbot_api_key=self.secrets_repo.get_chatbot_api_key(),
                code_snippet=request_data.code_snippet,
                prediction_prompt_text=request_data.user_prediction_prompt_text,
                user_prediction_text=request_data.user_prediction_text,
                user_explanation_text=request_data.user_explanation_text,
                actual_output_summary=request_data.actual_output_summary,
            )
            try:
                save_success = self.primm_submissions_table.save_submission(
                    user_id=user_id,
                    request_data=request_data,  # This is PrimmEvaluationRequestModel instance
                    evaluation_data=ai_eval_response,  # This is PrimmEvaluationResponseModel instance
                )
                if not save_success:
                    _LOGGER.error(f"Failed PRIMM submission save for {user_id}, ex. {request_data.primm_example_id}")
                    # Continue to return 200 to client as AI feedback was successful
            except Exception as db_save_ex:
                _LOGGER.error(f"Exception saving PRIMM submission for user {user_id}: {db_save_ex}", exc_info=True)

            return format_lambda_response(200, ai_eval_response.model_dump(by_alias=True, exclude_none=True))

    def handle(self, event: dict) -> dict:
        _LOGGER.info(f"PRIMMFeedback.handle invoked for path: {get_path(event)}, method: {get_method(event)}")
        user_id = get_user_id_from_event(event)
        if not user_id:
            return create_error_response(ErrorCode.AUTHENTICATION_FAILED, event=event)

        http_method = get_method(event).upper()
        _LOGGER.info(f"PrimmFeedbackApiHandler received method: {http_method} for user_id: {user_id}")

        try:
            if http_method == "POST":
                return self._handle_post_request(event, user_id)
            else:
                _LOGGER.warning(f"Unsupported HTTP method for /primm-feedback: {http_method}")
                return create_error_response(ErrorCode.METHOD_NOT_ALLOWED, event=event)

        except ThrottleRateLimitExceededException as te:
            _LOGGER.warning(f"Throttling limit hit for PRIMM feedback (user {user_id}): {te.limit_type} - {te.message}")
            self.metrics_manager.put_metric("ThrottledRequest", 1)
            return create_error_response(ErrorCode.RATE_LIMIT_EXCEEDED, event=event)
        except ChatBotApiError as ce:
            _LOGGER.error(f"AI Service communication error during PRIMM feedback: {str(ce)}", exc_info=True)
            self.metrics_manager.put_metric("ChatBotApiFailure", 1)
            return create_error_response(ErrorCode.AI_SERVICE_UNAVAILABLE, event=event)
        except Exception as e:
            _LOGGER.error(f"Unexpected error in PrimmFeedbackApiHandler: {str(e)}", exc_info=True)
            return create_error_response(ErrorCode.INTERNAL_ERROR, event=event)


# Global Lambda handler function
def primm_feedback_lambda_handler(event: dict, context: typing.Any) -> dict:
    _LOGGER.info(f"Global handler. Method: {event.get('httpMethod')}, Path: {event.get('path')}")
    _LOGGER.warning(event)
    metrics_manager = MetricsManager("ThoughtfulPython/Authentication")

    try:
        throttle_table = ThrottleTable(get_throttle_table_name())
        primm_submissions_table = PrimmSubmissionsTable(get_primm_submissions_table_name())
        secrets_repo = SecretsRepository()
        chatbot_wrapper = ChatBotWrapper()

        api_handler = PrimmFeedbackApiHandler(
            throttle_table=throttle_table,
            primm_submissions_table=primm_submissions_table,
            secrets_repo=secrets_repo,
            chatbot_wrapper=chatbot_wrapper,
            metrics_manager=metrics_manager,
        )
        return api_handler.handle(event)

    except Exception as e:
        _LOGGER.critical(f"Critical error in global handler setup: {str(e)}", exc_info=True)
        return create_error_response(ErrorCode.INTERNAL_ERROR)
    finally:
        metrics_manager.flush()
