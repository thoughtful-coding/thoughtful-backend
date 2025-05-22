#!/usr/bin/env python3
import json
import logging
import typing

from pydantic import ValidationError

from aws_src_sample.dynamodb.user_progress_table import (
    BatchCompletionsInputModel,
    UserProgressModel,
    UserProgressTable,
)
from aws_src_sample.utils.aws_env_vars import get_user_progress_table_name

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


# --- Module-Level Helper Functions (can be shared or kept here) ---
def _get_user_id_from_event(event: dict[str, typing.Any]) -> typing.Optional[str]:
    """Extracts user ID from Lambda event context (adapt to your authorizer)."""
    try:
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("claims", {}).get("sub")
        if user_id:
            return str(user_id)
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("principalId")
        if user_id:
            return str(user_id)
        _LOGGER.warning("User ID not found in authorizer context.")
        return None
    except Exception as e:
        _LOGGER.error("Error extracting user_id from event: %s", str(e))
        return None


def _format_lambda_response(
    status_code: int,
    body: typing.Any,
    additional_headers: typing.Optional[dict[str, str]] = None,
) -> dict[str, typing.Any]:
    """Formats API Gateway proxy responses."""
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",  # IMPORTANT: Restrict in production
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "OPTIONS,GET,PUT",  # For /progress route
    }
    if additional_headers:
        headers.update(additional_headers)
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(body) if body is not None else None,
    }


class UserProgressApiHandler:
    """Handles API requests for user progress."""

    def __init__(self, db_wrapper: UserProgressTable) -> None:
        self.db_wrapper = db_wrapper
        _LOGGER.info("UserProgressApiHandler initialized.")

    def _handle_get_request(self, event: dict[str, typing.Any], user_id: str) -> dict[str, typing.Any]:
        _LOGGER.info("Handler: Processing GET /progress for user_id: %s", user_id)
        try:
            progress_model = self.db_wrapper.get_progress(user_id=user_id)
            if progress_model:
                return _format_lambda_response(200, progress_model.model_dump())
            else:
                # Return a default empty state for a new user or user with no progress
                default_progress = UserProgressModel(userId=user_id, completion={}, penaltyEndTime=None)
                return _format_lambda_response(200, default_progress.model_dump())
        except Exception as e:
            _LOGGER.exception("Error handling GET /progress request for user_id: %s", user_id)
            error_message = str(e)
            if hasattr(e, "response") and "Error" in e.response and "Message" in e.response["Error"]:
                error_message = f"Database error: {e.response['Error']['Message']}"
            return _format_lambda_response(500, {"message": f"Failed to retrieve progress: {error_message}"})

    def _handle_put_request(self, event: dict[str, typing.Any], user_id: str) -> dict[str, typing.Any]:
        _LOGGER.info("Handler: Processing PUT /progress for user_id: %s", user_id)
        try:
            body_str = event.get("body")
            if not body_str:
                return _format_lambda_response(400, {"message": "Missing request body."})

            raw_payload = json.loads(body_str)
            # Validate incoming payload with Pydantic
            batch_input = BatchCompletionsInputModel.model_validate(raw_payload)
            _LOGGER.debug("Validated batch_input: %s", batch_input.model_dump_json(indent=2))

            if not batch_input.completions:  # Empty list is valid, but does nothing but update timestamp
                _LOGGER.info("Received empty completions list for user_id: %s. Only updating timestamp.", user_id)

            updated_progress_model = self.db_wrapper.update_progress(
                user_id=user_id, completions_to_add=batch_input.completions
            )

            return _format_lambda_response(200, updated_progress_model.model_dump())

        except json.JSONDecodeError:
            _LOGGER.exception("Invalid JSON in PUT /progress request body.")
            return _format_lambda_response(400, {"message": "Invalid JSON format in request body."})
        except ValidationError as ve:
            _LOGGER.warning("Invalid PUT /progress request payload: %s", ve.errors())
            return _format_lambda_response(400, {"message": "Invalid request payload.", "details": ve.errors()})
        except Exception as e:
            _LOGGER.exception("Unexpected error handling PUT /progress request for user_id: %s", user_id)
            error_message = str(e)
            if hasattr(e, "response") and "Error" in e.response and "Message" in e.response["Error"]:
                error_message = f"Database error: {e.response['Error']['Message']}"
            return _format_lambda_response(500, {"message": f"Failed to update progress: {error_message}"})

    def handle(self, event: dict[str, typing.Any], context: typing.Any) -> dict[str, typing.Any]:
        _LOGGER.info("UserProgressApiHandler.handle invoked. Event path: %s", event.get("path"))

        user_id = _get_user_id_from_event(event)
        if not user_id:
            return _format_lambda_response(401, {"message": "Unauthorized: User identification failed."})

        http_method = event.get("httpMethod", "").upper()
        _LOGGER.info("HTTP Method: %s for user_id: %s", http_method, user_id)

        if http_method == "GET":
            return self._handle_get_request(event, user_id)
        elif http_method == "PUT":
            return self._handle_put_request(event, user_id)
        else:
            _LOGGER.warning("Unsupported HTTP method for /progress: %s", http_method)
            return _format_lambda_response(405, {"message": f"HTTP method {http_method} not allowed on /progress."})


def user_progress_lambda_handler(event: dict[str, typing.Any], context: typing.Any) -> dict[str, typing.Any]:
    _LOGGER.debug("Global user_progress_lambda_handler received event.")
    print(event)
    try:
        uplh = UserProgressApiHandler(UserProgressTable(get_user_progress_table_name()))
        return uplh.handle(event, context)
    except Exception as e:
        _LOGGER.critical("Critical error in global progress handler or instantiation: %s", str(e), exc_info=True)
        return _format_lambda_response(500, {"message": f"Internal server error: {str(e)}"})
