import logging
import typing

from aws_src_sample.dynamodb.learning_entries_table import LearningEntriesTable
from aws_src_sample.dynamodb.primm_submissions_table import PrimmSubmissionsTable
from aws_src_sample.dynamodb.user_permissions_table import UserPermissionsTable
from aws_src_sample.dynamodb.user_progress_table import UserProgressTable
from aws_src_sample.models.instructor_portal_models import (
    ClassUnitProgressResponseModel,
    InstructorStudentInfoModel,
    ListOfInstructorStudentsResponseModel,
    StudentUnitCompletionDataModel,
)
from aws_src_sample.models.user_progress_models import UserUnitProgressModel
from aws_src_sample.utils.apig_utils import (
    format_lambda_response,
    get_method,
    get_path,
    get_user_id_from_event,
)
from aws_src_sample.utils.aws_env_vars import (
    get_learning_entries_table_name,
    get_primm_submissions_table_name,
    get_progress_table_name,
    get_user_permissions_table_name,
)
from aws_src_sample.utils.base_types import InstructorId, UnitId, UserId

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class InstructorPortalApiHandler:
    def __init__(
        self,
        user_permissions_table: UserPermissionsTable,
        progress_table: UserProgressTable,
        learning_entries_table: LearningEntriesTable,
        primm_submissions_table: PrimmSubmissionsTable,
    ):
        self.user_permissions_table = user_permissions_table
        self.progress_table = progress_table
        self.learning_entries_table = learning_entries_table
        self.primm_submissions_table = primm_submissions_table

    def _handle_get_instructor_students(self, instructor_id: InstructorId) -> dict:
        _LOGGER.info(f"Fetching permitted students for instructor_id: {instructor_id}")

        try:
            user_ids = self.user_permissions_table.get_permitted_student_ids_for_teacher(
                teacher_user_id=instructor_id,
                permission_type="VIEW_STUDENT_DATA_FULL",
            )

            student_infos: list[InstructorStudentInfoModel] = []
            for user_id in user_ids:
                student_infos.append(
                    InstructorStudentInfoModel(
                        studentId=user_id,
                        studentName=None,
                        studentEmail=None,
                    )
                )

            response_model = ListOfInstructorStudentsResponseModel(students=student_infos)
            return format_lambda_response(200, response_model.model_dump(by_alias=True, exclude_none=True))

        except Exception as e:
            _LOGGER.error(f"Error in for {instructor_id}: {e}", exc_info=True)
            return format_lambda_response(500, {"message": "An error occurred while fetching student list."})

    def _handle_get_class_unit_progress(self, instructor_id: InstructorId, unit_id: UnitId) -> dict:
        _LOGGER.info(f"Instructor {instructor_id} requesting class progress for unit {unit_id}")

        try:
            # 1. Get list of students the instructor is permitted to view
            permitted_user_ids = self.user_permissions_table.get_permitted_student_ids_for_teacher(
                teacher_user_id=instructor_id,
                permission_type="VIEW_STUDENT_DATA_FULL",
            )

            student_progress_data_list: list[StudentUnitCompletionDataModel] = []
            for user_id in permitted_user_ids:
                user_unit_progress = self.progress_table.get_user_unit_progress(
                    user_id=user_id,
                    unit_id=unit_id,
                )

                if user_unit_progress:
                    completion_map = user_unit_progress.completion
                else:
                    completion_map = {}

                student_progress_data_list.append(
                    StudentUnitCompletionDataModel(
                        studentId=user_id,
                        completedSectionsInUnit=completion_map,
                    )
                )

            response_payload = ClassUnitProgressResponseModel(
                unitId=unit_id, studentProgressData=student_progress_data_list
            )
            return format_lambda_response(200, response_payload.model_dump(by_alias=True, exclude_none=True))

        except Exception as e:
            _LOGGER.error(
                f"Error in _handle_get_class_unit_progress for instructor {instructor_id}, unit {unit_id}: {e}",
                exc_info=True,
            )
            return format_lambda_response(500, {"message": "An error occurred while fetching class unit progress."})

    def handle(self, event: dict) -> dict:
        # Extract instructor_user_id from the authenticated user
        user_id = get_user_id_from_event(event)
        if not user_id:
            _LOGGER.warning("Unauthorized: No user_id found in event.")
            return format_lambda_response(401, {"message": "Unauthorized: User identification failed."})
        instructor_id = InstructorId(user_id)

        http_method = get_method(event).upper()
        path = get_path(event)

        _LOGGER.info(f"Received method: {http_method}, path: {path}, instructor_id: {instructor_id}")

        try:
            if http_method == "GET" and path == "/instructor/students":
                return self._handle_get_instructor_students(instructor_id)

            elif http_method == "GET" and path.startswith("/instructor/units/") and path.endswith("/class-progress"):
                # Path: /instructor/units/{unitId}/class-progress
                parts = path.split("/")  # ['', 'instructor', 'units', unitId, 'class-progress']
                if (
                    len(parts) == 5
                    and parts[1] == "instructor"
                    and parts[2] == "units"
                    and parts[4] == "class-progress"
                ):
                    unit_id = UnitId(parts[3])
                    return self._handle_get_class_unit_progress(instructor_id, unit_id)
                else:
                    _LOGGER.warning(f"Malformed path for class unit progress: {path}")
                    return format_lambda_response(400, {"message": "Malformed URL for class unit progress."})

            # Placeholder for GET /instructor/students/{studentId}/units/{unitId}/progress
            # This endpoint would be very similar to _handle_get_class_unit_progress but for a single student
            # and would involve a permission check for that specific student first.
            # For now, the client will derive this from the batch class-progress endpoint.

            else:
                _LOGGER.warning(f"Unsupported path or method for Teacher Portal: {http_method} {path}")
                return format_lambda_response(404, {"message": "Resource not found or method not allowed."})

        except Exception as e:
            _LOGGER.error(
                f"Unexpected error in TeacherPortalApiHandler for instructor {instructor_id}: {str(e)}",
                exc_info=True,
            )
            return format_lambda_response(500, {"message": "An unexpected server error occurred."})


# Global Lambda handler function (remains mostly the same, ensures UserProgressTable DAL is passed)
def instructor_portal_lambda_handler(event: dict, context: typing.Any) -> dict:
    http_method = event.get("requestContext", {}).get("http", {}).get("method", "UNKNOWN_METHOD")
    path = event.get("requestContext", {}).get("http", {}).get("path", "UNKNOWN_PATH")
    _LOGGER.info(f"instructor_portal_lambda_handler invoked. Method: {http_method}, Path: {path}")

    try:
        api_handler = InstructorPortalApiHandler(
            user_permissions_table=UserPermissionsTable(get_user_permissions_table_name()),
            progress_table=UserProgressTable(get_progress_table_name()),
            learning_entries_table=LearningEntriesTable(get_learning_entries_table_name()),
            primm_submissions_table=PrimmSubmissionsTable(get_primm_submissions_table_name()),
        )
        return api_handler.handle(event)

    except Exception as e:
        _LOGGER.critical(f"Error in global handler setup: {str(e)}", exc_info=True)
        return format_lambda_response(500, {"message": f"Internal server error during handler setup."})
