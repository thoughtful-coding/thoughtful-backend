#!/usr/bin/env python3
import decimal
import json
from unittest.mock import Mock

from thoughtful_backend.lambdas.instructor_portal_lambda import InstructorPortalApiHandler
from thoughtful_backend.models.primm_feedback_models import StoredPrimmSubmissionItemModel

from ..test_utils.authorizer import add_authorizer_info


def create_instructor_portal_api_handler(
    user_permissions_table=Mock(),
    user_progress_table=Mock(),
    learning_entries_table=Mock(),
    primm_submissions_table=Mock(),
) -> InstructorPortalApiHandler:
    ret = InstructorPortalApiHandler(
        user_permissions_table=user_permissions_table,
        user_progress_table=user_progress_table,
        learning_entries_table=learning_entries_table,
        primm_submissions_table=primm_submissions_table,
    )

    assert ret.user_permissions_table == user_permissions_table
    assert ret.user_progress_table == user_progress_table
    assert ret.learning_entries_table == learning_entries_table
    assert ret.primm_submissions_table == primm_submissions_table
    return ret


def test_user_progress_api_handler_1():
    create_instructor_portal_api_handler()


def test_user_progress_api_handler_handle_error_1():
    """
    Unidentified user -> "User identification failed"
    """
    event = {}

    ret = create_instructor_portal_api_handler()
    response = ret.handle(event)

    assert response["statusCode"] == 401


def test_user_progress_api_handler_handle_error_2():
    """
    Improper/unhandled method -> "HTTP method not allow"
    """
    event = {"requestContext": {}}
    add_authorizer_info(event, "e")

    ret = create_instructor_portal_api_handler()
    response = ret.handle(event)

    assert response["statusCode"] == 404


def test_user_progress_api_handler_handle_get_1():
    event = {
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/instructor/other",
            }
        }
    }
    add_authorizer_info(event, "e")

    ret = create_instructor_portal_api_handler()
    response = ret.handle(event)

    assert response["statusCode"] == 404


def test_user_progress_api_handler_handle_get_2():
    event = {
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/instructor/students",
            }
        }
    }
    add_authorizer_info(event, "e")

    user_permissions_table = Mock()
    user_permissions_table.get_permitted_student_ids_for_teacher.return_value = ["p1"]
    ret = create_instructor_portal_api_handler(user_permissions_table=user_permissions_table)
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_dict = json.loads(response["body"])
    assert body_dict == {"students": [{"studentId": "p1"}]}


def test_user_progress_api_handler_handle_get_3():
    """
    Test trying to get data for unit progess when instructor has accesss to no students
    """
    event = {
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/instructor/units/u1/class-progress",
            }
        }
    }
    add_authorizer_info(event, "e")

    user_permissions_table = Mock()
    user_permissions_table.get_permitted_student_ids_for_teacher.return_value = []
    ret = create_instructor_portal_api_handler(user_permissions_table=user_permissions_table)
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_dict = json.loads(response["body"])
    assert body_dict == {"studentProgressData": [], "unitId": "u1"}


def test_user_progress_api_handler_handle_get_4():
    """
    Test trying to get data for unit progess when instructor has accesss to a bunch of students
    """
    event = {
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/instructor/units/u1/class-progress",
            }
        }
    }
    add_authorizer_info(event, "e")

    user_permissions_table = Mock()
    user_permissions_table.get_permitted_student_ids_for_teacher.return_value = ["s1"]
    user_progress_table = Mock()
    user_progress_table.get_user_unit_progress.return_value = {}
    ret = create_instructor_portal_api_handler(
        user_permissions_table=user_permissions_table,
        user_progress_table=user_progress_table,
    )
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_dict = json.loads(response["body"])
    assert body_dict == {"unitId": "u1", "studentProgressData": [{"studentId": "s1", "completedSectionsInUnit": {}}]}


def test_user_progress_api_handler_handle_get_5():
    """
    Test try to get data for a student who hasn't done the given unit
    """
    event = {
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/instructor/units/u1/class-progress",
            }
        }
    }
    add_authorizer_info(event, "e")

    user_permissions_table = Mock()
    user_permissions_table.get_permitted_student_ids_for_teacher.return_value = ["s1"]
    user_progress_table = Mock()
    user_progress_table.get_user_unit_progress.return_value = None
    ret = create_instructor_portal_api_handler(
        user_permissions_table=user_permissions_table,
        user_progress_table=user_progress_table,
    )
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_dict = json.loads(response["body"])
    assert body_dict == {"unitId": "u1", "studentProgressData": [{"studentId": "s1", "completedSectionsInUnit": {}}]}


def test_user_progress_api_handler_handle_get_6():
    """
    Test trying to get data for all student's learning entries w/o perms
    """
    event = {
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/instructor/students/s1/learning-entries",
            }
        }
    }
    add_authorizer_info(event, "e")

    user_permissions_table = Mock()
    user_permissions_table.check_permission.return_value = False
    learning_entries_table = Mock()
    learning_entries_table.get_finalized_entries_for_user.return_value = ([], None)
    ret = create_instructor_portal_api_handler(
        user_permissions_table=user_permissions_table,
        learning_entries_table=learning_entries_table,
    )
    response = ret.handle(event)

    assert response["statusCode"] == 403


def test_user_progress_api_handler_handle_get_7():
    """
    Test trying to get data for all student's learning entries w/o perms
    """
    event = {
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/instructor/students/s1/learning-entries",
            }
        }
    }
    add_authorizer_info(event, "e")

    user_permissions_table = Mock()
    user_permissions_table.check_permission.return_value = True
    learning_entries_table = Mock()
    learning_entries_table.get_entries_for_user.return_value = ([], None)
    ret = create_instructor_portal_api_handler(
        user_permissions_table=user_permissions_table,
        learning_entries_table=learning_entries_table,
    )
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_dict = json.loads(response["body"])
    assert body_dict == {"entries": [], "lastEvaluatedKey": None}


def test_user_progress_api_handler_handle_get_8():
    """
    Missing assignment type results in 400
    """
    event = {
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/instructor/units/u1/lessons/l1/sections/s1/assignment-submissions",
            }
        },
        "pathParameters": {"unitId": "u1", "lessonId": "l1", "sectionId": "s1"},
    }
    add_authorizer_info(event, "e")

    user_permissions_table = Mock()
    user_permissions_table.get_permitted_student_ids_for_teacher.return_value = ["s1"]
    learning_entries_table = Mock()
    learning_entries_table.get_versions_for_section.return_value = ([], None)
    ret = create_instructor_portal_api_handler(
        user_permissions_table=user_permissions_table,
        learning_entries_table=learning_entries_table,
    )
    response = ret.handle(event)

    assert response["statusCode"] == 400


def test_user_progress_api_handler_handle_get_9():
    """
    Missing assignment type results in 400
    """
    event = {
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/instructor/units/u1/lessons/l1/sections/s1/assignment-submissions",
            }
        },
        "pathParameters": {"unitId": "u1", "lessonId": "l1", "sectionId": "s1"},
        "queryStringParameters": {"assignmentType": "Reflection"},
    }
    add_authorizer_info(event, "e")

    user_permissions_table = Mock()
    user_permissions_table.get_permitted_student_ids_for_teacher.return_value = ["s1"]
    learning_entries_table = Mock()
    learning_entries_table.get_versions_for_section.return_value = ([], None)
    ret = create_instructor_portal_api_handler(
        user_permissions_table=user_permissions_table,
        learning_entries_table=learning_entries_table,
    )
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_dict = json.loads(response["body"])
    assert body_dict == {
        "assignmentType": "Reflection",
        "unitId": "u1",
        "lessonId": "l1",
        "sectionId": "s1",
        "primmExampleId": None,
        "submissions": [],
    }


def test_user_progress_api_handler_handle_get_10():
    """
    Missing assignment type results in 400
    """
    event = {
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/instructor/units/u1/lessons/l1/sections/s1/assignment-submissions",
            }
        },
        "pathParameters": {"unitId": "u1", "lessonId": "l1", "sectionId": "s1"},
        "queryStringParameters": {"assignmentType": "PRIMM", "primmExampleId": "4"},
    }
    add_authorizer_info(event, "e")

    user_permissions_table = Mock()
    user_permissions_table.get_permitted_student_ids_for_teacher.return_value = ["s1"]
    primm_submissions_table = Mock()
    primm_submission = StoredPrimmSubmissionItemModel(
        userId="eric.rizzi@gmail.com",
        submissionCompositeKey="03cff8d8-95340#primm-print-analysis#primm-greetings-line3#2025-06-06T20:21:48.433152+00:00",
        actualOutputSummary="Hello name it's nice to meet you!",
        aiExplanationAssessment="insufficient",
        aiOverallComment="It looks like there's a misunderstanding!",
        aiPredictionAssessment="insufficient",
        codeSnippet="# We'll use a fixed name for",
        createdAt="2025-06-06T20:21:48.433175+00:00",
        lessonId="03cff8d8-33a0-49ed-98c4-d51613995340",
        primmExampleId="primm-greetings-line3",
        sectionId="primm-print-analysis",
        timestampIso="2025-06-06T20:21:48.433152+00:00",
        userExplanationText="I was right.",
        userPredictionConfidence=decimal.Decimal(3),
        userPredictionPromptText="Look closely",
        userPredictionText='It will print out "hello alex"',
    )
    primm_submissions_table.get_submissions_by_student.return_value = ([primm_submission], None)
    ret = create_instructor_portal_api_handler(
        user_permissions_table=user_permissions_table,
        primm_submissions_table=primm_submissions_table,
    )
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_dict = json.loads(response["body"])
    assert body_dict["assignmentType"] == "PRIMM"
    assert body_dict["unitId"] == "u1"
    assert body_dict["lessonId"] == "l1"
    assert body_dict["sectionId"] == "s1"
    assert len(body_dict["submissions"]) == 1
    assert body_dict["submissions"][0]["submissionDetails"]["userPredictionConfidence"] == 3
