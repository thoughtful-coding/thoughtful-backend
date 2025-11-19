import logging
import typing

from thoughtful_backend.dynamodb.first_solutions_table import FirstSolutionsTable
from thoughtful_backend.dynamodb.learning_entries_table import LearningEntriesTable
from thoughtful_backend.dynamodb.primm_submissions_table import PrimmSubmissionsTable
from thoughtful_backend.dynamodb.user_permissions_table import UserPermissionsTable
from thoughtful_backend.dynamodb.user_progress_table import UserProgressTable
from thoughtful_backend.models.instructor_portal_models import (
    ClassUnitProgressResponseModel,
    InstructorStudentInfoModel,
    LessonProgressProfileModel,
    ListOfInstructorStudentsResponseModel,
    SectionStatusItemModel,
    StudentDetailedProgressResponseModel,
    StudentUnitCompletionDataModel,
    UnitProgressProfileModel,
)
from thoughtful_backend.models.learning_entry_models import ReflectionVersionItemModel
from thoughtful_backend.utils.apig_utils import (
    ErrorCode,
    create_error_response,
    format_lambda_response,
    get_last_evaluated_key,
    get_method,
    get_pagination_limit,
    get_path,
    get_path_parameters,
    get_query_string_parameters,
    get_user_id_from_event,
)
from thoughtful_backend.utils.aws_env_vars import (
    get_first_solutions_table_name,
    get_learning_entries_table_name,
    get_primm_submissions_table_name,
    get_user_permissions_table_name,
    get_user_progress_table_name,
)
from thoughtful_backend.utils.base_types import (
    InstructorId,
    LessonId,
    SectionId,
    UnitId,
    UserId,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class InstructorPortalApiHandler:
    def __init__(
        self,
        user_permissions_table: UserPermissionsTable,
        user_progress_table: UserProgressTable,
        learning_entries_table: LearningEntriesTable,
        primm_submissions_table: PrimmSubmissionsTable,
        first_solutions_table: FirstSolutionsTable,
    ):
        self.user_permissions_table = user_permissions_table
        self.user_progress_table = user_progress_table
        self.learning_entries_table = learning_entries_table
        self.primm_submissions_table = primm_submissions_table
        self.first_solutions_table = first_solutions_table

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
            return create_error_response(ErrorCode.INTERNAL_ERROR)

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
                user_unit_progress = self.user_progress_table.get_user_unit_progress(
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
            return create_error_response(ErrorCode.INTERNAL_ERROR)

    def _handle_get_student_learning_entries(
        self,
        instructor_id: InstructorId,
        student_id: UserId,
        event: dict,
    ) -> dict:
        """
        Handles an instructor's request to view a specific student's learning entries.
        Supports filtering by 'all', 'final', or 'drafts' via the ?filter query parameter.
        """
        _LOGGER.info(f"Instructor {instructor_id} requesting learning entries for student {student_id}")

        # 1. Permission Check: Ensure the instructor is allowed to view this student's data.
        has_permission = self.user_permissions_table.check_permission(
            granter_user_id=student_id,
            grantee_user_id=instructor_id,
            permission_type="VIEW_STUDENT_DATA_FULL",
        )
        if not has_permission:
            _LOGGER.warning(f"Forbidden: Instructor {instructor_id} lacks permission for student {student_id}.")
            return create_error_response(ErrorCode.AUTHORIZATION_FAILED, event=event)

        try:
            query_params = get_query_string_parameters(event)

            # Get filter parameter (default to 'all')
            filter_param = query_params.get("filter", "all")

            # Validate filter parameter
            if filter_param not in ["all", "final", "drafts"]:
                _LOGGER.warning(f"Invalid filter parameter: {filter_param}")
                return create_error_response(
                    ErrorCode.VALIDATION_ERROR,
                    f"Invalid filter parameter. Must be 'all', 'final', or 'drafts'.",
                    event=event,
                )

            entries, next_last_key = self.learning_entries_table.get_entries_for_user(
                user_id=student_id,
                filter_mode=filter_param,  # type: ignore
                limit=get_pagination_limit(query_params),
                last_evaluated_key=get_last_evaluated_key(query_params),
            )

            response_payload = {
                "entries": [item.model_dump(by_alias=True, exclude_none=True) for item in entries],
                "lastEvaluatedKey": next_last_key,
            }

            return format_lambda_response(200, response_payload)

        except Exception as e:
            _LOGGER.error(
                f"Error fetching learning entries for student {student_id}: {e}",
                exc_info=True,
            )
            return create_error_response(ErrorCode.INTERNAL_ERROR, event=event)

    def _handle_get_student_detailed_progress(
        self,
        instructor_id: InstructorId,
        student_id: UserId,
        event: dict,
    ) -> dict:
        """
        Handles an instructor's request to view a specific student's detailed progress
        across all units, lessons, and sections with submission details.
        """
        _LOGGER.info(f"Instructor {instructor_id} requesting detailed progress for student {student_id}")

        # 1. Permission Check
        has_permission = self.user_permissions_table.check_permission(
            granter_user_id=student_id,
            grantee_user_id=instructor_id,
            permission_type="VIEW_STUDENT_DATA_FULL",
        )
        if not has_permission:
            _LOGGER.warning(f"Forbidden: Instructor {instructor_id} lacks permission for student {student_id}.")
            return create_error_response(ErrorCode.AUTHORIZATION_FAILED, event=event)

        try:
            # 2. Get all user progress for this student
            all_progress = self.user_progress_table.get_all_unit_progress_for_user(user_id=student_id)

            if not all_progress:
                # No progress for this student
                response_model = StudentDetailedProgressResponseModel(
                    studentId=student_id,
                    studentName=None,
                    profile=[],
                )
                return format_lambda_response(200, response_model.model_dump(by_alias=True, exclude_none=True))

            # 3. Fetch all submissions once (optimized approach)
            # Get all reflection submissions for this student
            all_reflections, _ = self.learning_entries_table.get_entries_for_user(
                user_id=student_id,
                filter_mode="all",
            )

            # Get all PRIMM submissions for this student
            all_primm, _ = self.primm_submissions_table.get_submissions_by_student(
                user_id=student_id,
                lesson_id_filter=None,
                section_id_filter=None,
                primm_example_id_filter=None,
            )

            # 4. Build lookup maps for efficient access
            # Map: (lessonId, sectionId) -> list of reflection versions
            reflections_by_section: dict[tuple[LessonId, SectionId], list[ReflectionVersionItemModel]] = {}
            for reflection in all_reflections:
                key = (reflection.lessonId, reflection.sectionId)
                if key not in reflections_by_section:
                    reflections_by_section[key] = []
                reflections_by_section[key].append(reflection)

            # Map: (lessonId, sectionId) -> list of PRIMM submissions
            primm_by_section: dict[tuple[LessonId, SectionId], list] = {}
            for primm in all_primm:
                key = (primm.lessonId, primm.sectionId)
                if key not in primm_by_section:
                    primm_by_section[key] = []
                primm_by_section[key].append(primm)

            # 5. Build the response structure by iterating through progress
            profile_list: list[UnitProgressProfileModel] = []

            for progress_item in all_progress:
                unit_id = progress_item.unitId
                lessons_list: list[LessonProgressProfileModel] = []

                for lesson_id, sections_completion in progress_item.completion.items():
                    sections_list: list[SectionStatusItemModel] = []

                    for section_id, completion_detail in sections_completion.items():
                        section_key = (lesson_id, section_id)

                        # Check for Reflection submissions
                        if section_key in reflections_by_section:
                            reflection_versions = reflections_by_section[section_key]
                            # Sort by creation time, newest first
                            reflection_versions_sorted = sorted(
                                reflection_versions, key=lambda x: x.createdAt, reverse=True
                            )
                            sections_list.append(
                                SectionStatusItemModel(
                                    sectionId=section_id,
                                    sectionTitle="",  # Frontend will populate
                                    sectionKind="Reflection",
                                    status="submitted",
                                    submissionTimestamp=reflection_versions_sorted[0].createdAt,
                                    submissionDetails=[v.model_dump(by_alias=True) for v in reflection_versions_sorted],
                                )
                            )
                            continue

                        # Check for PRIMM submissions
                        if section_key in primm_by_section:
                            primm_submissions = primm_by_section[section_key]
                            # Sort by timestamp, newest first
                            primm_submissions_sorted = sorted(
                                primm_submissions, key=lambda x: x.timestampIso, reverse=True
                            )
                            sections_list.append(
                                SectionStatusItemModel(
                                    sectionId=section_id,
                                    sectionTitle="",  # Frontend will populate
                                    sectionKind="PRIMM",
                                    status="submitted",
                                    submissionTimestamp=primm_submissions_sorted[0].timestampIso,
                                    submissionDetails=[s.model_dump(by_alias=True) for s in primm_submissions_sorted],
                                )
                            )
                            continue

                        # Check for Testing submissions
                        # Query for this specific section
                        testing_solutions, _ = self.first_solutions_table.get_solutions_for_section(
                            unit_id=unit_id,
                            lesson_id=lesson_id,
                            section_id=section_id,
                        )
                        # Find this student's solution
                        student_solution = next(
                            (s for s in testing_solutions if s.get("userId") == student_id),
                            None,
                        )

                        if student_solution:
                            sections_list.append(
                                SectionStatusItemModel(
                                    sectionId=section_id,
                                    sectionTitle="",  # Frontend will populate
                                    sectionKind="Testing",
                                    status="submitted",
                                    submissionTimestamp=student_solution.get("submittedAt"),
                                    submissionDetails=student_solution,
                                )
                            )
                            continue

                        # No submission, just completed
                        if completion_detail.completedAt:
                            sections_list.append(
                                SectionStatusItemModel(
                                    sectionId=section_id,
                                    sectionTitle="",  # Frontend will populate
                                    sectionKind="",  # Unknown type
                                    status="completed",
                                    submissionTimestamp=completion_detail.completedAt,
                                    submissionDetails=None,
                                )
                            )

                    if sections_list:
                        lessons_list.append(
                            LessonProgressProfileModel(
                                lessonId=lesson_id,
                                lessonTitle="",  # Frontend will populate
                                sections=sections_list,
                            )
                        )

                if lessons_list:
                    profile_list.append(
                        UnitProgressProfileModel(
                            unitId=unit_id,
                            unitTitle="",  # Frontend will populate
                            lessons=lessons_list,
                        )
                    )

            response_model = StudentDetailedProgressResponseModel(
                studentId=student_id,
                studentName=None,  # Not available in current data
                profile=profile_list,
            )
            return format_lambda_response(200, response_model.model_dump(by_alias=True, exclude_none=True))

        except Exception as e:
            _LOGGER.error(
                f"Error fetching detailed progress for student {student_id}: {e}",
                exc_info=True,
            )
            return create_error_response(ErrorCode.INTERNAL_ERROR, event=event)

    def _handle_get_assignment_submissions(self, instructor_id: InstructorId, event: dict) -> dict:
        _LOGGER.info(f"Instructor {instructor_id} requesting submissions for a specific assignment.")

        try:
            path_params = get_path_parameters(event)
            query_params = get_query_string_parameters(event)

            unit_id = UnitId(path_params.get("unitId", ""))
            lesson_id = LessonId(path_params.get("lessonId", ""))
            section_id = SectionId(path_params.get("sectionId", ""))
            assignment_type = query_params.get("assignmentType")
            primm_example_id = query_params.get("primmExampleId")

            if not all([unit_id, lesson_id, section_id, assignment_type]):
                return create_error_response(
                    ErrorCode.VALIDATION_ERROR, "Missing required path or query parameters.", event=event
                )

            permitted_students = self.user_permissions_table.get_permitted_student_ids_for_teacher(instructor_id)
            if not permitted_students:
                return format_lambda_response(200, {"submissions": []})  # No students, so no submissions

            all_student_submissions = []
            if assignment_type == "Reflection":
                for student_id in permitted_students:
                    versions, _ = self.learning_entries_table.get_versions_for_section(
                        user_id=student_id,
                        lesson_id=lesson_id,
                        section_id=section_id,
                        filter_mode="all",
                    )
                    if versions:
                        # The rest of the logic remains the same
                        all_student_submissions.append(
                            {
                                "studentId": student_id,
                                "submissionTimestamp": versions[0].createdAt,
                                "submissionDetails": [v.model_dump(by_alias=True) for v in versions],
                            }
                        )

            elif assignment_type == "PRIMM":
                for student_id in permitted_students:
                    primm_submissions, _ = self.primm_submissions_table.get_submissions_by_student(
                        user_id=student_id,
                        lesson_id_filter=lesson_id,
                        section_id_filter=section_id,
                        primm_example_id_filter=primm_example_id,  # Optional - filters if provided
                    )
                    for sub in primm_submissions:
                        all_student_submissions.append(
                            {
                                "studentId": student_id,
                                "submissionTimestamp": sub.timestampIso,
                                "submissionDetails": sub.model_dump(by_alias=True),
                            }
                        )

            elif assignment_type == "Testing":
                # Query all first solutions for this section at once
                solutions, _ = self.first_solutions_table.get_solutions_for_section(
                    unit_id=unit_id,
                    lesson_id=lesson_id,
                    section_id=section_id,
                )
                # Filter to only include permitted students
                for solution in solutions:
                    student_id = solution.get("userId")
                    if student_id in permitted_students:
                        all_student_submissions.append(
                            {
                                "studentId": student_id,
                                "submissionTimestamp": solution.get("submittedAt"),
                                "submissionDetails": solution,
                            }
                        )

            else:
                raise ValueError(f"Unhandled assignment type: {assignment_type}")

            # Sort all collected submissions from all students by timestamp, newest first
            all_student_submissions.sort(key=lambda x: x["submissionTimestamp"], reverse=True)

            response_payload = {
                "assignmentType": assignment_type,
                "unitId": unit_id,
                "lessonId": lesson_id,
                "sectionId": section_id,
                "primmExampleId": primm_example_id,
                "submissions": all_student_submissions,
            }
            return format_lambda_response(200, response_payload)

        except Exception as e:
            _LOGGER.error(
                f"Error in _handle_get_assignment_submissions for instructor {instructor_id}: {e}", exc_info=True
            )
            return create_error_response(ErrorCode.INTERNAL_ERROR, event=event)

    def handle(self, event: dict) -> dict:
        # Extract instructor_user_id from the authenticated user
        user_id = get_user_id_from_event(event)
        if not user_id:
            _LOGGER.warning("Unauthorized: No user_id found in event.")
            return create_error_response(ErrorCode.AUTHENTICATION_FAILED, event=event)
        instructor_id = InstructorId(user_id)

        http_method = get_method(event).upper()
        path = get_path(event)
        path_parts = path.strip("/").split("/")

        _LOGGER.info(f"Received method: {http_method}, path: {path}, instructor_id: {instructor_id}")

        try:
            if http_method == "GET" and path == "/instructor/students":
                return self._handle_get_instructor_students(instructor_id)

            elif http_method == "GET" and path.startswith("/instructor/units/") and path.endswith("/class-progress"):
                # Path: /instructor/units/{unitId}/class-progress
                if (
                    len(path_parts) == 4
                    and path_parts[0] == "instructor"
                    and path_parts[1] == "units"
                    and path_parts[3] == "class-progress"
                ):
                    unit_id = UnitId(path_parts[2])
                    return self._handle_get_class_unit_progress(instructor_id, unit_id)
                else:
                    _LOGGER.warning(f"Malformed path for class unit progress: {path}")
                    return create_error_response(
                        ErrorCode.VALIDATION_ERROR, "Malformed URL for class unit progress.", event=event
                    )

            elif (
                http_method == "GET" and path.startswith("/instructor/students/") and path.endswith("/learning-entries")
            ):
                # Path: /instructor/students/{studentId}/learning-entries
                if len(path_parts) == 4:
                    student_id = UserId(path_parts[2])
                    return self._handle_get_student_learning_entries(instructor_id, student_id, event)
                else:
                    _LOGGER.warning(f"Malformed path for learning entries: {path}")
                    return create_error_response(
                        ErrorCode.VALIDATION_ERROR, "Malformed URL for finalized learning entries.", event=event
                    )

            elif (
                http_method == "GET"
                and path.startswith("/instructor/students/")
                and path.endswith("/detailed-progress")
            ):
                # Path: /instructor/students/{studentId}/detailed-progress
                if len(path_parts) == 4:
                    student_id = UserId(path_parts[2])
                    return self._handle_get_student_detailed_progress(instructor_id, student_id, event)
                else:
                    _LOGGER.warning(f"Malformed path for detailed progress: {path}")
                    return create_error_response(
                        ErrorCode.VALIDATION_ERROR, "Malformed URL for detailed progress.", event=event
                    )

            elif http_method == "GET" and len(path_parts) == 8 and path.endswith("/assignment-submissions"):
                # Matches /instructor/units/{unitId}/lessons/{lessonId}/sections/{sectionId}/assignment-submissions
                return self._handle_get_assignment_submissions(instructor_id, event)

            else:
                _LOGGER.warning(f"Unsupported path or method for Teacher Portal: {http_method} {path}")
                return create_error_response(ErrorCode.RESOURCE_NOT_FOUND, event=event)

        except Exception as e:
            _LOGGER.error(
                f"Unexpected error in TeacherPortalApiHandler for instructor {instructor_id}: {str(e)}",
                exc_info=True,
            )
            return create_error_response(ErrorCode.INTERNAL_ERROR, event=event)


# Global Lambda handler function (remains mostly the same, ensures UserProgressTable DAL is passed)
def instructor_portal_lambda_handler(event: dict, context: typing.Any) -> dict:
    http_method = event.get("requestContext", {}).get("http", {}).get("method", "UNKNOWN_METHOD")
    path = event.get("requestContext", {}).get("http", {}).get("path", "UNKNOWN_PATH")
    _LOGGER.info(f"instructor_portal_lambda_handler invoked. Method: {http_method}, Path: {path}")

    try:
        api_handler = InstructorPortalApiHandler(
            user_permissions_table=UserPermissionsTable(get_user_permissions_table_name()),
            user_progress_table=UserProgressTable(get_user_progress_table_name()),
            learning_entries_table=LearningEntriesTable(get_learning_entries_table_name()),
            primm_submissions_table=PrimmSubmissionsTable(get_primm_submissions_table_name()),
            first_solutions_table=FirstSolutionsTable(get_first_solutions_table_name()),
        )
        return api_handler.handle(event)

    except Exception as e:
        _LOGGER.critical(f"Error in global handler setup: {str(e)}", exc_info=True)
        return create_error_response(ErrorCode.INTERNAL_ERROR)
