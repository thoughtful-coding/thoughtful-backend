#!/usr/bin/env python3
import json
from unittest.mock import Mock

from aws_src_sample.lambdas.instructor_portal_lambda import InstructorPortalApiHandler


def add_authorizier_info(event: dict, user_id: str) -> None:
    assert "authorizer" not in event["requestContext"]
    event["requestContext"]["authorizer"] = {"jwt": {"claims": {"email": user_id}}}


def create_instructor_portal_api_handler(
    user_permissions_table=Mock(),
    progress_table=Mock(),
    learning_entries_table=Mock(),
    primm_submissions_table=Mock(),
) -> InstructorPortalApiHandler:
    ret = InstructorPortalApiHandler(
        user_permissions_table=user_permissions_table,
        progress_table=progress_table,
        learning_entries_table=learning_entries_table,
        primm_submissions_table=primm_submissions_table,
    )

    assert ret.user_permissions_table == user_permissions_table
    assert ret.progress_table == progress_table
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
    add_authorizier_info(event, "e")

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
    add_authorizier_info(event, "e")

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
    add_authorizier_info(event, "e")

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
    add_authorizier_info(event, "e")

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
    add_authorizier_info(event, "e")

    user_permissions_table = Mock()
    user_permissions_table.get_permitted_student_ids_for_teacher.return_value = ["s1"]
    progress_table = Mock()
    progress_table.get_user_unit_progress.return_value = {}
    ret = create_instructor_portal_api_handler(
        user_permissions_table=user_permissions_table,
        progress_table=progress_table,
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
    add_authorizier_info(event, "e")

    user_permissions_table = Mock()
    user_permissions_table.get_permitted_student_ids_for_teacher.return_value = ["s1"]
    progress_table = Mock()
    progress_table.get_user_unit_progress.return_value = None
    ret = create_instructor_portal_api_handler(
        user_permissions_table=user_permissions_table,
        progress_table=progress_table,
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
    add_authorizier_info(event, "e")

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
    add_authorizier_info(event, "e")

    user_permissions_table = Mock()
    user_permissions_table.check_permission.return_value = True
    learning_entries_table = Mock()
    learning_entries_table.get_finalized_entries_for_user.return_value = ([], None)
    ret = create_instructor_portal_api_handler(
        user_permissions_table=user_permissions_table,
        learning_entries_table=learning_entries_table,
    )
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_dict = json.loads(response["body"])
    assert body_dict == {"entries": [], "lastEvaluatedKey": None}
