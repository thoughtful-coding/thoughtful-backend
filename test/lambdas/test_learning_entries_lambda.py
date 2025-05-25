#!/usr/bin/env python3
import json
import os
from unittest.mock import Mock

from aws_src_sample.lambdas.learning_entries_lambda import LearningEntriesApiHandler


def add_authorizier_info(event: dict, user_id: str) -> None:
    assert "authorizer" not in event["requestContext"]
    event["requestContext"]["authorizer"] = {"jwt": {"claims": {"email": user_id}}}


def test_learning_entries_api_handler_1():
    learning_entries_table = Mock()
    secrets_manager = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager)
    assert ret.learning_entries_table == learning_entries_table
    assert ret.chatbot_secrets_manager == secrets_manager


def test_learning_entries_api_handler_handle_error_1():
    """
    Unidentified user -> "User identification failed"
    """
    event = {}

    learning_entries_table = Mock()
    secrets_manager = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager)
    response = ret.handle(event)

    assert response["statusCode"] == 401


def test_learning_entries_api_handler_handle_error_2():
    """
    Improper/unhandled method -> "HTTP method not allow"
    """
    event = {"requestContext": {}}
    add_authorizier_info(event, "e")

    learning_entries_table = Mock()
    secrets_manager = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager)
    response = ret.handle(event)

    assert response["statusCode"] == 405


def test_learning_entries_api_handler_handle_get_reflections_1():
    event = {
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/lessons/l1/sections/s1/reflections",
                "pathParameters": {"lessonId": "l1", "sectionId": "s1"},
            }
        },
    }
    add_authorizier_info(event, "e")

    learning_entries_table = Mock()
    learning_entries_table.get_draft_versions_for_section.return_value = ([], None)
    secrets_manager = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager)
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_list = json.loads(response["body"])
    assert body_list == {"versions": []}


def test_learning_entries_api_handler_handle_get_reflection_2():
    event = {
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/lessons/l1/sections/s1/reflections",
                "pathParameters": {"lessonId": "l1", "sectionId": "s1"},
                "queryStringParameters": {"limit": "10", "lastEvaluatedKey": "{}"},
            }
        },
    }
    add_authorizier_info(event, "e")

    learning_entries_table = Mock()
    learning_entries_table.get_draft_versions_for_section.return_value = ([], None)
    secrets_manager = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager)
    breakpoint()
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_list = json.loads(response["body"])
    assert body_list == {"versions": []}


def test_learning_entries_api_handler_handle_get_finalized_1():
    event = {
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/learning-entries",
            }
        },
    }
    add_authorizier_info(event, "e")

    learning_entries_table = Mock()
    learning_entries_table.get_finalized_entries_for_user.return_value = ([], None)
    secrets_manager = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager)
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_list = json.loads(response["body"])
    assert body_list == {"entries": []}


def test_learning_entries_api_handler_handle_get_finalized_2():
    event = {
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/learning-entries",
            }
        },
    }
    add_authorizier_info(event, "e")

    learning_entries_table = Mock()
    learning_entries_table.get_finalized_entries_for_user.return_value = ([], None)
    secrets_manager = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager)
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_list = json.loads(response["body"])
    assert body_list == {"entries": []}


def test_learning_entries_api_handler_handle_post_1():
    """
    Handle missing body
    """
    event = {"requestContext": {"http": {"method": "POST"}}}
    add_authorizier_info(event, "e")

    learning_entries_table = Mock()
    secrets_manager = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager)
    response = ret.handle(event)

    assert response["statusCode"] == 400
    assert response["body"] == '{"message": "Missing request body."}'


def test_learning_entries_api_handler_handle_post_2():
    """
    Handle bad body
    """
    event = {"requestContext": {"http": {"method": "POST"}}, "body": "a"}
    add_authorizier_info(event, "e")

    learning_entries_table = Mock()
    secrets_manager = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager)
    response = ret.handle(event)

    assert response["statusCode"] == 400
    assert response["body"] == '{"message": "Invalid JSON format in request body."}'


def test_learning_entries_api_handler_handle_post_3():
    """
    Handle proper input
    """
    entry_json = {
        "submissionTopic": "Things to think",
        "submissionCode": "for i in range",
        "submissionExplanation": "goes around",
        "aiFeedback": "Good job",
        "aiAssessment": "mostly",
    }
    event = {"requestContext": {"http": {"method": "POST"}}, "body": json.dumps(entry_json)}
    add_authorizier_info(event, "e")

    learning_entries_table = Mock()
    learning_entries_table.add_entry.return_value = LearningEntryResponseModel(
        userId="e",
        entryId="uuid_h",
        submissionTopic="Things to think",
        submissionCode="for i in range",
        submissionExplanation="goes around",
        aiFeedback="Good job",
        aiAssessment="mostly",
        createdAt="2025-05-26",
    )
    secrets_manager = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager)
    response = ret.handle(event)

    assert response["statusCode"] == 201
    body_dict = json.loads(response["body"])
    assert body_dict["success"] == True
    assert body_dict["message"] == "Learning entry submitted successfully."
