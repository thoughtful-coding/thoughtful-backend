#!/usr/bin/env python3
import json
import os
from unittest.mock import Mock

from aws_src_sample.dynamodb.learning_entries_table import LearningEntryResponseModel
from aws_src_sample.lambdas.learning_entries_lambda import LearningEntriesApiHandler


def add_authorizier_info(event: dict, user_id: str) -> None:
    assert "authorizer" not in event["requestContext"]
    event["requestContext"]["authorizer"] = {"jwt": {"claims": {"email": user_id}}}


def test_learning_entries_api_handler_1():
    ret = LearningEntriesApiHandler("1")
    assert ret.learning_entries_table == "1"


def test_learning_entries_api_handler_handle_error_1():
    """
    Unidentified user -> "User identification failed"
    """
    event = {}

    learning_entries_table = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table)
    response = ret.handle(event)

    assert response["statusCode"] == 401


def test_learning_entries_api_handler_handle_error_2():
    """
    Improper/unhandled method -> "HTTP method not allow"
    """
    event = {"requestContext": {}}
    add_authorizier_info(event, "e")

    learning_entries_table = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table)
    response = ret.handle(event)

    assert response["statusCode"] == 405


def test_learning_entries_api_handler_handle_get_1():
    event = {"requestContext": {"http": {"method": "GET"}}}
    add_authorizier_info(event, "e")

    learning_entries_table = Mock()
    learning_entries_table.get_entries_by_user.return_value = []
    ret = LearningEntriesApiHandler(learning_entries_table)
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_list = json.loads(response["body"])
    assert body_list == []


def test_learning_entries_api_handler_handle_get_2():
    event = {"requestContext": {"http": {"method": "GET"}}}
    add_authorizier_info(event, "e")

    learning_entries_table = Mock()
    learning_entries_table.get_entries_by_user.return_value = [
        LearningEntryResponseModel(
            userId="e",
            entryId="uuid_h",
            submissionTopic="Things to think",
            submissionCode="for i in range",
            submissionExplanation="goes around",
            aiFeedback="Good job",
            aiAssessment="mostly",
            createdAt="2025-05-26",
        )
    ]
    ret = LearningEntriesApiHandler(learning_entries_table)
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_list = json.loads(response["body"])
    assert len(body_list) == 1
    assert body_list[0]["userId"] == "e"
    assert body_list[0]["entryId"] == "uuid_h"


def test_learning_entries_api_handler_handle_post_1():
    """
    Handle missing body
    """
    event = {"requestContext": {"http": {"method": "POST"}}}
    add_authorizier_info(event, "e")

    learning_entries_table = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table)
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
    ret = LearningEntriesApiHandler(learning_entries_table)
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

    ret = LearningEntriesApiHandler(learning_entries_table)
    response = ret.handle(event)

    assert response["statusCode"] == 201
    body_dict = json.loads(response["body"])
    assert body_dict["success"] == True
    assert body_dict["message"] == "Learning entry submitted successfully."
