import json
import logging
import typing

from pydantic import ValidationError

from thoughtful_backend.dynamodb.user_progress_table import UserProgressTable
from thoughtful_backend.models.user_progress_models import (
    BatchCompletionsInputModel,
    SectionCompletionDetail,
    UserProgressModel,
    UserUnitProgressModel,
)
from thoughtful_backend.utils.apig_utils import (
    ErrorCode,
    create_error_response,
    format_lambda_response,
    get_method,
    get_path,
    get_user_id_from_event,
)
from thoughtful_backend.utils.aws_env_vars import get_user_progress_table_name
from thoughtful_backend.utils.base_types import (
    IsoTimestamp,
    LessonId,
    SectionId,
    UnitId,
    UserId,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class UserProgressApiHandler:
    def __init__(self, user_progress_table: UserProgressTable):
        self.user_progress_table = user_progress_table

    def _aggregate_unit_progresses_for_user(self, user_id: UserId) -> UserProgressModel:
        """
        Fetches all unit-specific progress items for a user and aggregates them
        into a single UserProgressModel.
        """
        progress_items: list[UserUnitProgressModel] = self.user_progress_table.get_all_unit_progress_for_user(user_id)

        aggregated_completion: dict[UnitId, dict[LessonId, dict[SectionId, SectionCompletionDetail]]] = {}

        for unit_progress_item in progress_items:
            if unit_progress_item.completion:
                aggregated_completion[unit_progress_item.unitId] = unit_progress_item.completion

        return UserProgressModel(userId=user_id, completion=aggregated_completion)

    def _handle_get_request(self, user_id: UserId) -> dict:
        _LOGGER.info(f"Fetching aggregated progress for user_id: {user_id}")
        aggregated_progress_model = self._aggregate_unit_progresses_for_user(user_id)
        return format_lambda_response(200, aggregated_progress_model.model_dump(by_alias=True, exclude_none=True))

    def _handle_put_request(self, event: dict, user_id: UserId) -> dict:
        _LOGGER.info(f"Updating progress for user_id: {user_id}")
        try:
            raw_body = event.get("body")
            if not raw_body:
                _LOGGER.error("Request body is missing for progress update.")
                return create_error_response(ErrorCode.VALIDATION_ERROR, "Request body is missing.", event=event)

            batch_input = BatchCompletionsInputModel.model_validate_json(raw_body)

            if not batch_input.completions:
                _LOGGER.info(f"No completions provided in PUT request for user {user_id}. Returning current progress.")
            else:
                self.user_progress_table.batch_update_user_progress(user_id, batch_input.completions)
                _LOGGER.info(f"Batch update processed for user {user_id}.")

            # After updates, fetch and return the complete aggregated progress
            # This ensures the client gets the full, consistent state.
            aggregated_progress_model = self._aggregate_unit_progresses_for_user(user_id)
            return format_lambda_response(200, aggregated_progress_model.model_dump(by_alias=True, exclude_none=True))

        except ValidationError as e:
            _LOGGER.error(f"Progress update request body validation error: {e.errors()}", exc_info=True)
            return create_error_response(ErrorCode.VALIDATION_ERROR, details=e.errors(), event=event)
        except json.JSONDecodeError:
            _LOGGER.error("Progress update request body is not valid JSON.", exc_info=True)
            return create_error_response(ErrorCode.VALIDATION_ERROR, event=event)

    def handle(self, event: dict) -> dict:
        user_id = get_user_id_from_event(event)
        if not user_id:
            return create_error_response(ErrorCode.AUTHENTICATION_FAILED, event=event)

        http_method = get_method(event).upper()
        path = get_path(event)

        _LOGGER.info(f"UserProgressApiHandler: {http_method} {path} for user: {user_id}")

        try:
            if http_method == "GET" and path == "/progress":
                return self._handle_get_request(user_id)
            elif http_method == "PUT" and path == "/progress":
                return self._handle_put_request(event, user_id)
            else:
                _LOGGER.warning(f"Unsupported path or method for User Progress: {http_method} {path}")
                return create_error_response(ErrorCode.RESOURCE_NOT_FOUND, event=event)

        except Exception as e:
            _LOGGER.error(f"Unexpected error in UserProgressApiHandler for user {user_id}: {str(e)}", exc_info=True)
            return create_error_response(ErrorCode.INTERNAL_ERROR, event=event)


def user_progress_lambda_handler(event: dict[str, typing.Any], context: typing.Any) -> dict[str, typing.Any]:
    _LOGGER.debug("Global user_progress_lambda_handler received event.")
    _LOGGER.warning(event)

    try:
        api_handler = UserProgressApiHandler(
            user_progress_table=UserProgressTable(get_user_progress_table_name()),
        )
        return api_handler.handle(event)

    except ValueError as ve:
        _LOGGER.critical(f"Configuration error in user_progress_lambda_handler: {str(ve)}", exc_info=True)
        return create_error_response(ErrorCode.INTERNAL_ERROR, "Server configuration error")
    except Exception as e:
        _LOGGER.critical(f"Error during UserProgressApiHandler: {str(e)}", exc_info=True)
        return create_error_response(ErrorCode.INTERNAL_ERROR)
