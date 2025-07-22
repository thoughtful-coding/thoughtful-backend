import datetime
import json
import logging
import typing

from pydantic import ValidationError

from aws_src_sample.cloudwatch.metrics import MetricsManager
from aws_src_sample.dynamodb.learning_entries_table import LearningEntriesTable
from aws_src_sample.dynamodb.throttle_table import (
    ThrottleRateLimitExceededException,
    ThrottleTable,
)
from aws_src_sample.models.learning_entry_models import (
    ListOfFinalLearningEntriesResponseModel,
    ListOfReflectionDraftsResponseModel,
    ReflectionInteractionInputModel,
    ReflectionVersionItemModel,
)
from aws_src_sample.secrets_manager.secrets_repository import SecretsRepository
from aws_src_sample.utils.apig_utils import (
    QueryParams,
    format_lambda_response,
    get_last_evaluated_key,
    get_method,
    get_pagination_limit,
    get_path,
    get_path_parameters,
    get_query_string_parameters,
    get_user_id_from_event,
)
from aws_src_sample.utils.aws_env_vars import (
    get_learning_entries_table_name,
    get_throttle_table_name,
)
from aws_src_sample.utils.base_types import LessonId, SectionId, UserId
from aws_src_sample.utils.chatbot_utils import ChatBotApiError, ChatBotWrapper

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class LearningEntriesApiHandler:
    def __init__(
        self,
        learning_entries_table: LearningEntriesTable,
        throttle_table: ThrottleTable,
        secrets_repo: SecretsRepository,
        chatbot_wrapper: ChatBotWrapper,
        metrics_manager: MetricsManager,
    ):
        self.learning_entries_table = learning_entries_table
        self.throttle_table = throttle_table
        self.secrets_repo = secrets_repo
        self.chatbot_wrapper = chatbot_wrapper
        self.metrics_manager = metrics_manager

    def _process_draft_submission(
        self,
        interaction_input: ReflectionInteractionInputModel,
        *,
        user_id: UserId,
        lesson_id: LessonId,
        section_id: SectionId,
    ) -> ReflectionVersionItemModel:
        """
        Handles draft submissions (`isFinal: false`): gets AI feedback, saves a new draft.
        """
        _LOGGER.info(f"Processing DRAFT submission for {user_id}, {lesson_id}#{section_id}")

        with self.throttle_table.throttle_action(user_id, "REFLECTION_FEEDBACK_CHATBOT_API_CALL"):
            ai_response = self.chatbot_wrapper.call_reflection_api(
                chatbot_api_key=self.secrets_repo.get_chatbot_api_key(),
                topic=interaction_input.userTopic,
                is_topic_predefined=interaction_input.isUserTopicPredefined,
                code=interaction_input.userCode,
                is_code_predefined=interaction_input.isUserCodePredefined,
                explanation=interaction_input.userExplanation,
            )

        timestamp_dt = datetime.datetime.now(datetime.timezone.utc)
        version_id_sk_format = f"{lesson_id}#{section_id}#{timestamp_dt.isoformat().replace('+00:00', 'Z')}"

        draft_ddb_item_data = {
            "versionId": version_id_sk_format,
            "userId": user_id,
            "lessonId": lesson_id,
            "sectionId": section_id,
            "userTopic": interaction_input.userTopic,
            "userCode": interaction_input.userCode,
            "userExplanation": interaction_input.userExplanation,
            "aiFeedback": ai_response.aiFeedback,
            "aiAssessment": ai_response.aiAssessment,
            "createdAt": timestamp_dt,
            "isFinal": False,
            "sourceVersionId": None,  # Drafts usually don't have a source this way
            "finalEntryCreatedAt": None,
        }

        # Create and validate Pydantic model for DDB item
        reflection_ddb_item = ReflectionVersionItemModel(**draft_ddb_item_data)
        return self.learning_entries_table.save_item(reflection_ddb_item)

    def _process_final_submission(
        self,
        interaction_input: ReflectionInteractionInputModel,
        *,
        user_id: UserId,
        lesson_id: LessonId,
        section_id: SectionId,
    ) -> ReflectionVersionItemModel:
        """
        Handles final submissions (`isFinal: true`).
        """
        _LOGGER.info(f"Processing FINAL submission for {user_id}, {lesson_id}#{section_id}")

        actual_source_version_id = interaction_input.sourceVersionId
        if not actual_source_version_id:
            _LOGGER.info("sourceVersionId not provided by client for final submission, finding most recent draft.")
            source_draft_model = self.learning_entries_table.get_most_recent_draft_for_section(
                user_id, lesson_id, section_id
            )
            if not source_draft_model:
                raise ValueError("Cannot finalize: No prior draft found. Please get feedback on a draft first.")
            actual_source_version_id = source_draft_model.versionId
            # The qualifying AI feedback/assessment are on this source_draft_model,
            # but as per user's clarification, they are not copied onto the final DDB record's
            # aiFeedback/aiAssessment fields. The enrichment happens for GET /learning-entries.
            # For the purpose of storing the final item itself, its own aiFeedback/Assessment are null.
        else:  # Client provided sourceVersionId, validate it
            source_draft_model = self.learning_entries_table.get_version_by_id(user_id, actual_source_version_id)
            if not source_draft_model or source_draft_model.isFinal:
                raise ValueError(f"Invalid sourceVersionId '{actual_source_version_id}' or it's not a draft.")

        # Ensure the source draft (wherever it came from) had AI feedback
        if source_draft_model.aiFeedback is None or source_draft_model.aiAssessment is None:
            _LOGGER.error(
                f"Source draft {actual_source_version_id} for finalization is missing AI feedback/assessment."
            )
            raise ValueError("The source draft for finalization is incomplete.")

        timestamp_dt = datetime.datetime.now(datetime.timezone.utc)
        final_version_id_sk = f"{lesson_id}#{section_id}#{timestamp_dt.isoformat().replace('+00:00', 'Z')}"

        final_item_ddb_data = {
            "versionId": final_version_id_sk,
            "userId": user_id,
            "lessonId": lesson_id,
            "sectionId": section_id,
            "userTopic": interaction_input.userTopic,
            "userCode": interaction_input.userCode,
            "userExplanation": interaction_input.userExplanation,
            "aiFeedback": None,  # Final entry itself has no *new* AI feedback
            "aiAssessment": None,  # Final entry itself has no *new* AI assessment
            "createdAt": timestamp_dt,
            "isFinal": True,
            "sourceVersionId": actual_source_version_id,  # Link to the draft
            "finalEntryCreatedAt": timestamp_dt.isoformat().replace("+00:00", "Z"),  # For GSI
        }

        final_reflection_ddb_item = ReflectionVersionItemModel(**final_item_ddb_data)
        saved_final_ddb_item = self.learning_entries_table.save_item(final_reflection_ddb_item)

        # As per Swagger's oneOf, for isFinal=true, the response is the created final item.
        # The GET /learning-entries is responsible for enrichment if client needs it that way.
        # Your latest Swagger POST response for isFinal=true was FinalizedLearningEntryResponseEnriched.
        # If we need to return that here, we'd do the enrichment now.
        # Let's stick to the "non-enriched on GET" for now, meaning POST for final just returns the created final ReflectionVersionItemModel.
        return saved_final_ddb_item

    def _handle_get_draft_versions(
        self,
        user_id: UserId,
        lesson_id: LessonId,
        section_id: SectionId,
        query_params: typing.Optional[QueryParams],
    ) -> ListOfReflectionDraftsResponseModel:
        _LOGGER.info(f"Fetching DRAFT versions for {user_id}, {lesson_id}#{section_id}")
        draft_ddb_items, next_last_key = self.learning_entries_table.get_versions_for_section(
            user_id,
            lesson_id,
            section_id,
            limit=get_pagination_limit(query_params),
            last_evaluated_key=get_last_evaluated_key(query_params),
        )
        # The DAL already returns Pydantic models (ReflectionVersionItemModel)
        return ListOfReflectionDraftsResponseModel(versions=draft_ddb_items, lastEvaluatedKey=next_last_key)

    def _handle_get_finalized_entries(
        self,
        user_id: UserId,
        query_params: typing.Optional[QueryParams],
    ) -> ListOfFinalLearningEntriesResponseModel:
        _LOGGER.info(f"Fetching FINALIZED entries for user {user_id}")

        # DAL returns ReflectionVersionItemModel instances where isFinal=true
        final_ddb_items, next_last_key = self.learning_entries_table.get_finalized_entries_for_user(
            user_id,
            limit=get_pagination_limit(query_params),
            last_evaluated_key=get_last_evaluated_key(query_params),
        )

        # As per user: GET /learning-entries is NOT enriched. It returns ReflectionVersionItemModel list.
        return ListOfFinalLearningEntriesResponseModel(entries=final_ddb_items, lastEvaluatedKey=next_last_key)

    def _route_get_request(self, event: dict, user_id: UserId) -> dict:
        _LOGGER.info("Handling GET request")
        path = get_path(event)
        path_params = get_path_parameters(event)
        query_params = get_query_string_parameters(event)

        if path == "/learning-entries":
            response_model = self._handle_get_finalized_entries(user_id, query_params)
            return format_lambda_response(200, response_model.model_dump(exclude_none=True))
        elif path.startswith("/reflections/") and path_params.get("lessonId") and path_params.get("sectionId"):
            lesson_id = LessonId(path_params["lessonId"])
            section_id = SectionId(path_params["sectionId"])
            response_model = self._handle_get_draft_versions(user_id, lesson_id, section_id, query_params)
            return format_lambda_response(200, response_model.model_dump(exclude_none=True))
        else:
            _LOGGER.warning(f"No hit for path: {path}, pp: {path_params}, qp: {query_params}")
            return format_lambda_response(404, {"message": "Resource not found."})

    def _route_post_request(self, event: dict, user_id: UserId) -> dict:
        _LOGGER.info("Handling POST request")
        path = get_path(event)
        path_params = get_path_parameters(event)

        if path.startswith("/reflections/") and path_params.get("lessonId") and path_params.get("sectionId"):
            lesson_id = LessonId(path_params["lessonId"])
            section_id = SectionId(path_params["sectionId"])

            try:
                raw_body = event.get("body") or "{}"
                # Validate request body with Pydantic
                interaction_input = ReflectionInteractionInputModel.model_validate_json(raw_body)
            except ValidationError as e:
                _LOGGER.error(f"Request body validation error: {e.errors()}", exc_info=True)
                return format_lambda_response(400, {"message": "Invalid request body."})
            except json.JSONDecodeError:
                _LOGGER.error("Request body is not valid JSON.", exc_info=True)
                return format_lambda_response(400, {"message": "Invalid JSON format in request body."})

            if interaction_input.isFinal:
                # Process final submission
                model = self._process_final_submission(
                    interaction_input, user_id=user_id, lesson_id=lesson_id, section_id=section_id
                )
            else:
                # Process draft submission
                model = self._process_draft_submission(
                    interaction_input, user_id=user_id, lesson_id=lesson_id, section_id=section_id
                )
            return format_lambda_response(201, model.model_dump(exclude_none=True))

        else:
            _LOGGER.warning(f"No hit for path: {path}, pp: {path_params}")
            return format_lambda_response(404, {"message": "Resource not found."})

    def handle(self, event: dict) -> dict:
        _LOGGER.info(f"Learning.handle invoked for path: {get_path(event)}, method: {get_method(event)}")
        user_id = get_user_id_from_event(event)
        if not user_id:
            return format_lambda_response(401, {"message": "Unauthorized: User identification failed."})

        http_method = get_method(event)
        _LOGGER.info("HTTP Method: %s for user_id: %s", http_method, user_id)

        try:
            if http_method == "GET":
                return self._route_get_request(event, user_id)
            elif http_method == "POST":
                return self._route_post_request(event, user_id)
            else:
                _LOGGER.warning("Unsupported HTTP method for /learning-entries: %s", http_method)
                return format_lambda_response(405, {"message": f"HTTP method not allowed on /progress."})

        except ValueError as ve:
            _LOGGER.warning(f"ValueError in handler: {str(ve)}", exc_info=False)
            return format_lambda_response(400, {"message": "ValueError handling incoming data."})
        except ThrottleRateLimitExceededException as te:
            _LOGGER.warning(f"Throttling: {te.limit_type} for user {user_id} - {te.message}")
            self.metrics_manager.put_metric("ThrottledRequest", 1)
            return format_lambda_response(429, {"message": "Throttling limit hit for Reflection feedback"})
        except ChatBotApiError as ce:
            _LOGGER.error(f"AI Service Error in handler: {str(ce)}", exc_info=True)
            self.metrics_manager.put_metric("ChatBotApiFailure", 1)
            return format_lambda_response(ce.status_code, {"message": "AI service communication error."})
        except Exception as e:
            _LOGGER.error(f"Unexpected error in API handler: {str(e)}", exc_info=True)
            return format_lambda_response(500, {"message": "An unexpected server error occurred."})


def learning_entries_lambda_handler(event: dict, context: typing.Any) -> dict:
    _LOGGER.info(f"Global handler. Method: {event.get('httpMethod')}, Path: {event.get('path')}")
    _LOGGER.warning(event)
    metrics_manager = MetricsManager("ThoughtfulPython/Authentication")

    try:
        learning_entries_table = LearningEntriesTable(get_learning_entries_table_name())
        throttle_table = ThrottleTable(get_throttle_table_name())
        secrets_repo = SecretsRepository()
        chatbot_wrapper = ChatBotWrapper()

        api_handler = LearningEntriesApiHandler(
            learning_entries_table=learning_entries_table,
            throttle_table=throttle_table,
            secrets_repo=secrets_repo,
            chatbot_wrapper=chatbot_wrapper,
            metrics_manager=metrics_manager,
        )
        return api_handler.handle(event)

    except Exception as e:
        _LOGGER.critical(f"Critical error in global handler setup: {str(e)}", exc_info=True)
        return format_lambda_response(500, {"message": f"Internal server error during handler setup."})
    finally:
        metrics_manager.flush()
