# src/aws_src_sample/lambdas/teacher_portal_api_lambda.py
import logging
import typing

from aws_src_sample.dynamodb.learning_entries_table import LearningEntriesTable
from aws_src_sample.dynamodb.primm_submissions_table import PrimmSubmissionsTable
from aws_src_sample.dynamodb.user_permissions_table import UserPermissionsTable
from aws_src_sample.dynamodb.user_progress_table import UserProgressTable
from aws_src_sample.models.instructor_portal_models import (
    InstructorStudentInfoModel,
    ListOfInstructorStudentsResponseModel,
)
from aws_src_sample.utils.apig_utils import (
    format_lambda_response,
    get_method,
    get_path,
    get_user_id_from_event,
)
from aws_src_sample.utils.aws_env_vars import (
    get_learning_entries_table_name,
    get_primm_submissions_table_name,
    get_user_permissions_table_name,
    get_user_progress_table_name,
)
from aws_src_sample.utils.base_types import InstructorId

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class InstructorPortalApiHandler:
    def __init__(
        self,
        user_permissions_table: UserPermissionsTable,
        user_progress_table: UserProgressTable,
        learning_entries_table: LearningEntriesTable,
        primm_submissions_table: PrimmSubmissionsTable,
    ):
        self.user_permissions_table = user_permissions_table
        self.user_progress_table = user_progress_table
        self.learning_entries_table = learning_entries_table
        self.primm_submissions_table = primm_submissions_table

    def _handle_get_instructor_students(self, instructor_user_id: InstructorId) -> dict:
        _LOGGER.info(f"Fetching permitted students for instructor_id: {instructor_user_id}")

        try:
            student_ids = self.user_permissions_table.get_permitted_student_ids_for_teacher(
                teacher_user_id=instructor_user_id,
                permission_type="VIEW_STUDENT_DATA_FULL",
            )

            student_infos: list[InstructorStudentInfoModel] = []
            for s_id in student_ids:
                # For POC, we just have studentId. Name/email enrichment is a future step.
                student_infos.append(InstructorStudentInfoModel(studentId=s_id, studentEmail=None, studentName=None))

            response_model = ListOfInstructorStudentsResponseModel(students=student_infos)
            return format_lambda_response(200, response_model.model_dump(by_alias=True, exclude_none=True))

        except Exception as e:  # Catch any errors from DAL or list processing
            _LOGGER.error(f"Error in for {instructor_user_id}: {e}", exc_info=True)
            return format_lambda_response(500, {"message": "An error occurred while fetching student list."})

    def handle(self, event: dict) -> dict:
        # Extract instructor_user_id from the authenticated user
        user_id = get_user_id_from_event(event)
        if not user_id:
            _LOGGER.warning("Unauthorized: No user_id found in event.")
            return format_lambda_response(401, {"message": "Unauthorized: User identification failed."})
        instructor_id = InstructorId(user_id)

        http_method = get_method(event).upper()
        path = get_path(event)

        _LOGGER.info(f"Received method: {http_method}, path: {path} for instructor_id: {instructor_id}")

        try:
            if http_method == "GET" and path == "/instructor/students":
                return self._handle_get_instructor_students(instructor_id)
            else:
                _LOGGER.warning(f"Unsupported path or method: {http_method} {path}")
                return format_lambda_response(404, {"message": "Resource not found or method not allowed."})

        except Exception as e:
            _LOGGER.error(f"Unexpected error in for instructor {instructor_id}: {str(e)}", exc_info=True)
            return format_lambda_response(500, {"message": "An unexpected server error occurred."})


def instructor_portal_lambda_handler(event: dict, context: typing.Any) -> dict:
    _LOGGER.info(f"Global handler. Method: {event.get('httpMethod')}, Path: {event.get('path')}")
    _LOGGER.warning(event)

    try:
        user_permissions_table = UserPermissionsTable(get_user_permissions_table_name())
        user_progress_table = UserProgressTable(get_user_progress_table_name())
        learning_entries_table = LearningEntriesTable(get_learning_entries_table_name())
        primm_submissions_table = PrimmSubmissionsTable(get_primm_submissions_table_name())

        api_handler = InstructorPortalApiHandler(
            user_permissions_table=user_permissions_table,
            user_progress_table=user_progress_table,
            learning_entries_table=learning_entries_table,
            primm_submissions_table=primm_submissions_table,
        )
        return api_handler.handle(event)

    except Exception as e:
        _LOGGER.critical(f"Critical error in global handler setup: {str(e)}", exc_info=True)
        return format_lambda_response(500, {"message": f"Internal server error during handler setup."})
