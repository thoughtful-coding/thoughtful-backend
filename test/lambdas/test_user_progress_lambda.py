# test/lambdas/test_user_progress_lambda.py
import json
import typing
from unittest.mock import Mock

from thoughtful_backend.lambdas.user_progress_lambda import UserProgressApiHandler
from thoughtful_backend.models.user_progress_models import (
    IsoTimestamp,
    LessonId,
    SectionCompletionInputModel,
    SectionId,
    UnitId,
    UserId,
    UserUnitProgressModel,
)

from ..test_utils.authorizer import add_authorizer_info


def create_progress_event(
    user_id_str: str,
    method: str = "GET",
    path: str = "/progress",
    body: typing.Optional[dict] = None,
) -> dict:
    """Helper to create a mock API Gateway event for /progress."""
    event_body = json.dumps(body) if body is not None else None
    event = {
        "requestContext": {"http": {"method": method, "path": path}},
        "body": event_body,
    }
    add_authorizer_info(event, user_id_str)
    return event


def create_user_progress_api_handler(
    progress_table=Mock(),
) -> UserProgressApiHandler:
    handler = UserProgressApiHandler(
        progress_table=progress_table,
    )
    assert handler.progress_table == progress_table
    return handler


def test_handler_initialization():
    create_user_progress_api_handler()


def test_handle_unauthorized_access():
    """
    Test response when user_id is not found in the event.
    """
    event = {"requestContext": {"http": {"method": "GET", "path": "/progress"}}}

    handler = create_user_progress_api_handler()
    response = handler.handle(event)

    assert response["statusCode"] == 401
    assert "User identification failed" in json.loads(response["body"])["message"]


def test_handle_unsupported_http_method():
    """
    Test response for an unhandled HTTP method
    """
    user_id_str = "user_unsupported_method"
    event = create_progress_event(user_id_str, method="DELETE")

    handler = create_user_progress_api_handler()
    response = handler.handle(event)

    assert response["statusCode"] == 404
    assert "Resource not found or method not allowed" in json.loads(response["body"])["message"]


def test_handle_get_progress_for_new_user():
    """
    Test GET /progress when the user has no existing progress records
    """
    user_id_str = "new_user_get_progress"
    event = create_progress_event(user_id_str, method="GET")

    progress_table = Mock()
    progress_table.get_all_unit_progress_for_user.return_value = []

    handler = create_user_progress_api_handler(progress_table=progress_table)
    response = handler.handle(event)

    assert response["statusCode"] == 200
    response_body = json.loads(response["body"])
    assert response_body["userId"] == user_id_str
    assert response_body["completion"] == {}
    progress_table.get_all_unit_progress_for_user.assert_called_once_with(UserId(user_id_str))


def test_handle_get_progress_for_existing_user():
    """
    Test GET /progress for a user with existing progress in multiple units
    """
    user_id_str = "existing_user_get_progress"
    event = create_progress_event(user_id_str, method="GET")

    unit1_id_str = "math101"
    lesson1_guid_str = "lesson_guid_algebra"
    section1_id_str = "section_vars"
    timestamp1 = "2025-06-03"

    unit2_id_str = "history101"
    lesson2_guid_str = "lesson_guid_ww2"
    section2_id_str = "section_causes"
    timestamp2 = "2025-06-04"

    progress_list = [
        UserUnitProgressModel(
            userId=UserId(user_id_str),
            unitId=UnitId(unit1_id_str),
            completion={LessonId(lesson1_guid_str): {SectionId(section1_id_str): IsoTimestamp(timestamp1)}},
        ),
        UserUnitProgressModel(
            userId=UserId(user_id_str),
            unitId=UnitId(unit2_id_str),
            completion={LessonId(lesson2_guid_str): {SectionId(section2_id_str): IsoTimestamp(timestamp2)}},
        ),
    ]
    progress_table = Mock()
    progress_table.get_all_unit_progress_for_user.return_value = progress_list

    handler = create_user_progress_api_handler(progress_table=progress_table)
    response = handler.handle(event)

    assert response["statusCode"] == 200
    response_body = json.loads(response["body"])
    assert response_body["userId"] == user_id_str
    expected_completion = {
        unit1_id_str: {lesson1_guid_str: {section1_id_str: timestamp1}},
        unit2_id_str: {lesson2_guid_str: {section2_id_str: timestamp2}},
    }
    assert response_body["completion"] == expected_completion
    progress_table.get_all_unit_progress_for_user.assert_called_once_with(UserId(user_id_str))


def test_handle_put_progress_missing_body():
    """
    Test PUT /progress with no request body
    """

    user_id_str = "put_user_no_body"
    event = create_progress_event(user_id_str, method="PUT", body=None)

    handler = create_user_progress_api_handler()
    response = handler.handle(event)

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["message"] == "Request body is missing."


def test_handle_put_progress_invalid_json():
    """
    Test PUT /progress with a non-JSON request body
    """

    user_id_str = "put_user_bad_json"
    event = create_progress_event(user_id_str, method="PUT", body={})
    event["body"] = "this is definitely not json"

    handler = create_user_progress_api_handler()
    response = handler.handle(event)

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["message"] == "Invalid request for progress update."


def test_handle_put_progress_validation_error():
    """
    Test PUT /progress with a payload that fails Pydantic validation
    """
    user_id_str = "put_user_validation_error"
    invalid_payload = {"completions": [{"sectionId": "sec_incomplete"}]}
    event = create_progress_event(user_id_str, method="PUT", body=invalid_payload)

    handler = create_user_progress_api_handler()
    response = handler.handle(event)

    assert response["statusCode"] == 400
    response_body = json.loads(response["body"])
    assert response_body["message"] == "Invalid request for progress update."
    assert "details" in response_body


def test_handle_put_progress_successful_update():
    """
    Test a successful PUT /progress operation
    """

    user_id_str = "put_user_success"
    unit_id1_str = "unit_for_put1"
    lesson_guid1_str = "lesson_guid_put1"
    section_id1_str = "section_put1"

    unit_id2_str = "unit_for_put2"
    lesson_guid2_str = "lesson_guid_put2"
    section_id2_str = "section_put2"

    completions_payload = {
        "completions": [
            {"unitId": unit_id1_str, "lessonId": lesson_guid1_str, "sectionId": section_id1_str},
            {"unitId": unit_id2_str, "lessonId": lesson_guid2_str, "sectionId": section_id2_str},
        ]
    }
    event = create_progress_event(user_id_str, method="PUT", body=completions_payload)

    progress_table = Mock()
    progress_table.batch_update_user_progress.return_value = {}

    # Mock what get_all_unit_progress_for_user returns *after* the update
    timestamp = "2025-06-04"
    mock_aggregated_response_state = [
        UserUnitProgressModel(
            userId=UserId(user_id_str),
            unitId=UnitId(unit_id1_str),
            completion={LessonId(lesson_guid1_str): {SectionId(section_id1_str): IsoTimestamp(timestamp)}},
        ),
        UserUnitProgressModel(
            userId=UserId(user_id_str),
            unitId=UnitId(unit_id2_str),
            completion={LessonId(lesson_guid2_str): {SectionId(section_id2_str): IsoTimestamp(timestamp)}},
        ),
    ]
    progress_table.get_all_unit_progress_for_user.return_value = mock_aggregated_response_state

    handler = create_user_progress_api_handler(progress_table=progress_table)
    response = handler.handle(event)

    assert response["statusCode"] == 200
    response_body = json.loads(response["body"])
    assert response_body["userId"] == user_id_str
    assert response_body["completion"][unit_id1_str][lesson_guid1_str][section_id1_str] == timestamp
    assert response_body["completion"][unit_id2_str][lesson_guid2_str][section_id2_str] == timestamp

    # Verify DAL calls
    expected_completions_input = [
        SectionCompletionInputModel(
            unitId=UnitId(unit_id1_str), lessonId=LessonId(lesson_guid1_str), sectionId=SectionId(section_id1_str)
        ),
        SectionCompletionInputModel(
            unitId=UnitId(unit_id2_str), lessonId=LessonId(lesson_guid2_str), sectionId=SectionId(section_id2_str)
        ),
    ]
    progress_table.batch_update_user_progress.assert_called_once_with(UserId(user_id_str), expected_completions_input)
    progress_table.get_all_unit_progress_for_user.assert_called_once_with(UserId(user_id_str))
