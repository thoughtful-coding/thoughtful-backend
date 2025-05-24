#!/usr/bin/env python3
import json
import logging
import typing

from pydantic import ValidationError

from aws_src_sample.dynamodb.learning_entries_table import (
    LearningEntriesTable,
    LearningEntryModel,
    LearningEntrySubmissionPayloadModel,
)
from aws_src_sample.utils.apig_utils import (
    format_lambda_response,
    get_method,
    get_user_id_from_event,
)
from aws_src_sample.utils.aws_env_vars import get_learning_entries_table_name

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class LearningEntriesApiHandler:
    """
    Handles API requests for learning entries.
    """

    def __init__(self, learning_entries_table: LearningEntriesTable) -> None:
        """
        Initializes the handler with a DynamoDB wrapper.
        :param learning_entries_table: An instance of LearningEntriesTable for DB operations.
        """
        self.learning_entries_table = learning_entries_table
        _LOGGER.info("LearningEntriesApiHandler initialized.")

    def _handle_get_request(self, event: dict[str, typing.Any], user_id: str) -> dict[str, typing.Any]:
        _LOGGER.info("Handler: Processing GET request for user_id: %s", user_id)
        try:
            query_params = event.get("queryStringParameters") or {}
            lesson_id_filter = query_params.get("lessonId")
            section_id_filter = query_params.get("sectionId")
            _LOGGER.debug("Query params: lessonId=%s, sectionId=%s", lesson_id_filter, section_id_filter)

            target_user_id_for_query = user_id  # Default for student fetching their own

            # Example if path indicates an instructor route and needs different user_id logic
            # path = event.get("path", "")
            # if path.startswith("/instructor/") and "studentId" in query_params:
            #    # Ensure current user (from token via user_id) is an authorized instructor!
            #    target_user_id_for_query = query_params["studentId"]

            entry_models: list[LearningEntryModel] = self.learning_entries_table.get_entries_by_user(
                user_id=target_user_id_for_query, lesson_id_filter=lesson_id_filter, section_id_filter=section_id_filter
            )

            response_items = [entry.model_dump() for entry in entry_models]
            return format_lambda_response(200, response_items)

        except Exception as e:
            _LOGGER.exception("Unexpected error handling GET request.")
            error_message = str(e)
            if (
                hasattr(e, "response") and "Error" in e.response and "Message" in e.response["Error"]
            ):  # Boto3 ClientError
                error_message = f"Database error: {e.response['Error']['Message']}"
            return format_lambda_response(500, {"message": f"An unexpected error occurred: {error_message}"})

    def _handle_post_request(self, event: dict[str, typing.Any], user_id: str) -> dict[str, typing.Any]:
        _LOGGER.info("Handler: Processing POST request for user_id: %s", user_id)
        try:
            body_str = event.get("body")
            if not body_str:
                return format_lambda_response(400, {"message": "Missing request body."})

            raw_payload = json.loads(body_str)
            entry_payload = LearningEntrySubmissionPayloadModel.model_validate(raw_payload)
            _LOGGER.debug("Validated entry_payload: %s", entry_payload.model_dump_json(indent=2))

            created_entry_model = self.learning_entries_table.add_entry(user_id=user_id, payload=entry_payload)

            return format_lambda_response(
                201,
                {
                    "success": True,
                    "entryId": created_entry_model.entryId,
                    "message": "Learning entry submitted successfully.",
                },
            )

        except json.JSONDecodeError:
            _LOGGER.exception("Invalid JSON in POST request body.")
            return format_lambda_response(400, {"message": "Invalid JSON format in request body."})
        except ValidationError as ve:
            _LOGGER.warning("Invalid request payload: %s", ve.errors())
            return format_lambda_response(400, {"message": "Invalid request payload.", "details": ve.errors()})
        except ValueError as ve:
            _LOGGER.warning("Value error creating entry: %s", str(ve))
            return format_lambda_response(400, {"message": str(ve)})
        except Exception as e:
            _LOGGER.exception("Unexpected error handling POST request.")
            # Avoid leaking too many details in general exceptions if ClientError from DDB wrapper is not caught specifically
            error_message = str(e)
            if (
                hasattr(e, "response") and "Error" in e.response and "Message" in e.response["Error"]
            ):  # Boto3 ClientError
                error_message = f"Database error: {e.response['Error']['Message']}"
            return format_lambda_response(500, {"message": f"An unexpected error occurred: {error_message}"})

    def handle(self, event: dict[str, typing.Any]) -> dict[str, typing.Any]:
        """
        Main entry point for the handler class.
        """
        _LOGGER.info("LearningEntriesApiHandler.handle invoked. Event %s", str(event))

        user_id = get_user_id_from_event(event)
        if not user_id:
            return format_lambda_response(401, {"message": "Unauthorized: User identification failed."})

        http_method = get_method(event).upper()
        _LOGGER.info("HTTP Method: %s for user_id: %s", http_method, user_id)

        if http_method == "GET":
            return self._handle_get_request(event, user_id)
        elif http_method == "POST":
            return self._handle_post_request(event, user_id)
        else:
            _LOGGER.warning("Unsupported HTTP method received: %s", http_method)
            return format_lambda_response(405, {"message": f"HTTP method {http_method} not allowed."})


def learning_entries_lambda_handler(
    event: typing.Dict[str, typing.Any], context: typing.Any
) -> typing.Dict[str, typing.Any]:
    """
    AWS Lambda entry point.
    """
    _LOGGER.warning(event)

    try:
        leh = LearningEntriesApiHandler(
            LearningEntriesTable(get_learning_entries_table_name()),
        )
        return leh.handle(event)
    except Exception as e:
        # Catch-all for errors during handler instantiation (e.g., table name env var missing)
        _LOGGER.critical("Critical error in global handler or instantiation: %s", str(e), exc_info=True)
        return format_lambda_response(500, {"message": f"Internal server error: {str(e)}"})
