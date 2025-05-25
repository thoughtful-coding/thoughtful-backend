import datetime
import json
import logging
import typing

# boto3 is available in Lambda environment by default
from botocore.exceptions import ClientError
from pydantic import ValidationError

from aws_src_sample.dynamodb.learning_entries_table import (
    LearningEntriesTable,
    ReflectionVersionItemModel,
)
from aws_src_sample.secrets_manager.chatbot_secrets import ChatBotSecrets
from aws_src_sample.utils.apig_utils import (
    format_lambda_response,
    get_user_id_from_event,
)
from aws_src_sample.utils.aws_env_vars import (
    get_chatbot_secrets_name,
    get_learning_entries_table_name,
)
from aws_src_sample.utils.chatbot_utils import call_google_genai_api

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


class LearningEntriesApiHandler:
    def __init__(
        self,
        learning_entries_table: LearningEntriesTable,
        chatbot_secrets: ChatBotSecrets,
    ):
        self.learning_entries_table = learning_entries_table
        self.chatbot_secrets = chatbot_secrets

    def _process_draft_submission(
        self,
        request_body: dict,
        *,
        user_id: str,
        lesson_id: str,
        section_id: str,
    ) -> dict:
        """
        Handles draft submissions (`isFinal: false`): gets AI feedback, saves a new draft.
        Returns the data payload for ReflectionFeedbackAndDraftResponse.
        """
        chatbot_api_key = self.chatbot_secrets.get_secret_value("CHATBOT_API_KEY")
        if not chatbot_api_key:
            raise KeyError("Couldn't find CHATBOT_API_KEY")

        user_topic = request_body.get("userTopic", "")
        user_code = request_body.get("userCode", "")
        user_explanation = request_body.get("userExplanation", "")
        ai_response_data = call_google_genai_api(
            chatbot_api_key=chatbot_api_key,
            topic=user_topic,
            code=user_code,
            explanation=user_explanation,
        )

        timestamp_dt = datetime.datetime.now().replace(tzinfo=datetime.timezone.utc)
        # Create versionId (DynamoDB SK format) using the full ISO string with 'Z'
        version_id_sk_format = f"{lesson_id}#{section_id}#{timestamp_dt.isoformat().replace('+00:00', 'Z')}"

        draft_data_for_model = {
            "versionId": version_id_sk_format,
            "userId": user_id,
            "lessonId": lesson_id,
            "sectionId": section_id,
            "userTopic": user_topic,
            "userCode": user_code,
            "userExplanation": user_explanation,
            "aiFeedback": ai_response_data.feedback,
            "aiAssessment": ai_response_data.assessment_level,
            "createdAt": timestamp_dt,  # Pass datetime object for Pydantic validator
            "isFinal": False,
            "sourceVersionId": None,
            "finalEntryCreatedAt": None,
        }

        try:
            reflection_version_item = ReflectionVersionItemModel(**draft_data_for_model)
        except ValidationError as e:
            _LOGGER.error(f"Pydantic validation error for draft item: {e}", exc_info=True)
            raise ValueError(f"Invalid data constructing reflection draft: {e}")

        saved_draft_item_model = self.learning_entries_table.save_item(reflection_version_item)

        response_payload = {
            "draftEntry": saved_draft_item_model.model_dump(exclude_none=True),  # Pydantic V2
            "currentAiFeedback": ai_response_data.feedback,
            "currentAiAssessment": ai_response_data.assessment_level,
        }
        return response_payload

    def _process_final_submission(
        self,
        request_body: dict,
        *,
        user_id: str,
        lesson_id: str,
        section_id: str,
    ) -> dict:
        """
        Handles final submissions (`isFinal: true`): creates a new final entry, referencing a source draft.
        Returns the data payload for FinalizedLearningEntryResponseEnriched.
        (This is a stub for Step 4 - will be fully implemented then)
        """
        _LOGGER.info(f"Processing FINAL submission for {user_id}, {lesson_id}#{section_id}")

        # Step 4 TODO:
        # 1. If sourceVersionId is not provided by client, look up the most recent draft:
        #    source_draft_model = self.entry_repository.get_most_recent_draft_for_section(user_id, lesson_id, section_id)
        #    if not source_draft_model:
        #        raise ValueError("Cannot finalize: No prior draft with AI feedback found.")
        #    actual_source_version_id = source_draft_model.versionId
        #    qualifying_ai_feedback = source_draft_model.aiFeedback
        #    qualifying_ai_assessment = source_draft_model.aiAssessment
        # Elif sourceVersionId *is* provided by client:
        #    source_draft_model = self.entry_repository.get_version_by_id(user_id, source_version_id)
        #    if not source_draft_model or source_draft_model.isFinal: # Must be a draft
        #        raise ValueError(f"Invalid sourceVersionId '{source_version_id}' or it's not a draft.")
        #    actual_source_version_id = source_draft_model.versionId
        #    qualifying_ai_feedback = source_draft_model.aiFeedback
        #    qualifying_ai_assessment = source_draft_model.aiAssessment

        # 2. Create new final_item_data_for_model using submission_content for userTopic, userCode, userExplanation
        #    Set isFinal=True, aiFeedback=None, aiAssessment=None
        #    Set sourceVersionId = actual_source_version_id
        #    Set finalEntryCreatedAt = new timestamp (same as createdAt for this final record)
        #    final_item_model = ReflectionVersionItemModel(**final_item_data_for_model)
        #    saved_final_item_model = self.entry_repository.save_item(final_item_model)

        # 3. Prepare FinalizedLearningEntryResponseEnriched payload:
        #    entryId = saved_final_item_model.versionId
        #    user data from saved_final_item_model
        #    qualifyingAiFeedback = qualifying_ai_feedback (from source draft)
        #    qualifyingAiAssessment = qualifying_ai_assessment (from source draft)
        #    createdAt = saved_final_item_model.createdAt
        #    sourceVersionId = actual_source_version_id

        # For now, returning a placeholder indicating not implemented for Step 3
        raise NotImplementedError("Final submission processing (Step 4) is not yet implemented.")

    def handle_post_request(self, event: dict, user_id: str) -> dict:
        """
        Main handler method for the class. Parses event, routes to specific processing methods.
        """
        try:
            path_params = event.get("pathParameters", {})
            lesson_id = path_params.get("lessonId")
            section_id = path_params.get("sectionId")

            if not lesson_id or not section_id:
                return format_lambda_response(400, {"message": "Missing lessonId or sectionId in path."})

            try:
                request_body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return format_lambda_response(400, {"message": "Invalid JSON in request body."})

            # Validate common required fields based on ReflectionInteractionInput
            # (userTopic, userCode, userExplanation)
            if not all(k in request_body for k in ["userTopic", "userCode", "userExplanation"]):
                return format_lambda_response(
                    400, {"message": "Missing required fields in body: userTopic, userCode, userExplanation."}
                )

            is_final_submission = request_body.get("isFinal", False)
            if is_final_submission:
                # This is where Step 4 logic will be fully integrated.
                # For now, it's stubbed to reflect it's not part of Step 3's primary focus.
                _LOGGER.info("Routing to final submission logic (currently stubbed for Step 3).")
                # Call _process_final_submission which will raise NotImplementedError for now
                response_data = self._process_final_submission(
                    request_body, user_id=user_id, lesson_id=lesson_id, section_id=section_id
                )
                # The status code for successfully creating a final entry is 201
                return format_lambda_response(201, response_data)
            else:
                # Process as a draft submission for AI feedback
                response_data = self._process_draft_submission(
                    request_body, user_id=user_id, lesson_id=lesson_id, section_id=section_id
                )
                # Swagger: oneOf ReflectionFeedbackAndDraftResponse or FinalizedLearningEntryResponseEnriched
                # This path returns ReflectionFeedbackAndDraftResponse
                return format_lambda_response(201, response_data)

        except ValidationError as ve:  # Pydantic validation error
            _LOGGER.error(f"Pydantic ValidationError in handler: {str(ve)}", exc_info=True)
            return format_lambda_response(400, {"message": f"Invalid input data: {ve.errors()}"})
        except ValueError as ve:
            _LOGGER.error(f"ValueError in handler: {str(ve)}", exc_info=True)
            return format_lambda_response(400, {"message": str(ve)})
        except (ConnectionError, TimeoutError) as ce:
            _LOGGER.error(f"AI Service Error in handler: {str(ce)}", exc_info=True)
            status_code = 504 if isinstance(ce, TimeoutError) else 503
            return format_lambda_response(status_code, {"message": f"AI service communication error: {str(ce)}"})
        except ClientError as e:
            _LOGGER.error(f"DynamoDB ClientError in handler: {e.response['Error']['Message']}", exc_info=True)
            return format_lambda_response(500, {"message": f"Database error: {e.response['Error']['Message']}"})
        except NotImplementedError as nie:  # Specific for stubbed final submission
            _LOGGER.warning(str(nie))
            return format_lambda_response(501, {"message": str(nie)})
        except Exception as e:
            _LOGGER.error(f"Unexpected error in handler: {str(e)}", exc_info=True)
            return format_lambda_response(500, {"message": f"An unexpected server error occurred."})

    def handle(self, event: dict[str, typing.Any]) -> dict[str, typing.Any]:
        _LOGGER.info(f"Lambda_handler invoked. Event (first 500 chars): {str(event)[:500]}")

        user_id = get_user_id_from_event(event)
        if not user_id:
            return format_lambda_response(401, {"message": "Unauthorized: User identification failed."})

        http_method = event.get("httpMethod")
        if http_method == "POST":
            return self.handle_post_request(event, user_id)
        else:
            _LOGGER.warning("Unsupported HTTP method for /progress: %s", http_method)
            return format_lambda_response(405, {"message": f"HTTP method {http_method} not allowed on /progress."})


def learning_entries_lambda_handler(event: dict[str, typing.Any], context: typing.Any) -> dict[str, typing.Any]:
    _LOGGER.debug("Global learning_entries_lambda_handler received event.")
    _LOGGER.warning(event)

    try:
        leah = LearningEntriesApiHandler(
            LearningEntriesTable(get_learning_entries_table_name()),
            ChatBotSecrets(get_chatbot_secrets_name()),
        )
        return leah.handle(event)
    except Exception as e:
        _LOGGER.critical("Critical error in global progress handler or instantiation: %s", str(e), exc_info=True)
        return format_lambda_response(500, {"message": f"Internal server error: {str(e)}"})
