#!/usr/bin/env python3
import json
from unittest.mock import Mock

from aws_src_sample.lambdas.learning_entries_lambda import LearningEntriesApiHandler
from aws_src_sample.models.learning_entry_models import ReflectionVersionItemModel
from aws_src_sample.utils.chatbot_utils import ChatBotFeedback


def add_authorizier_info(event: dict, user_id: str) -> None:
    assert "authorizer" not in event["requestContext"]
    event["requestContext"]["authorizer"] = {"jwt": {"claims": {"email": user_id}}}


def test_learning_entries_api_handler_1():
    learning_entries_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager, chatbot_wrapper)
    assert ret.learning_entries_table == learning_entries_table
    assert ret.chatbot_secrets_manager == secrets_manager
    assert ret.chatbot_wrapper == chatbot_wrapper


def test_learning_entries_api_handler_handle_error_1():
    """
    Unidentified user -> "User identification failed"
    """
    event = {}

    learning_entries_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager, chatbot_wrapper)
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
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager, chatbot_wrapper)
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
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager, chatbot_wrapper)
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
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager, chatbot_wrapper)
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
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager, chatbot_wrapper)
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
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager, chatbot_wrapper)
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_list = json.loads(response["body"])
    assert body_list == {"entries": []}


def test_learning_entries_api_handler_handle_put_reflection_1():
    """
    Handle missing body
    """
    event = {
        "requestContext": {
            "http": {
                "method": "PUT",
                "path": "/lessons/l1/sections/s1/reflections",
                "pathParameters": {"lessonId": "l1", "sectionId": "s1"},
            }
        },
    }
    add_authorizier_info(event, "e")

    learning_entries_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager, chatbot_wrapper)
    response = ret.handle(event)

    assert response["statusCode"] == 400


def test_learning_entries_api_handler_handle_put_reflection_2():
    """
    Handle bad body
    """
    event = {
        "requestContext": {
            "http": {
                "method": "PUT",
                "path": "/lessons/l1/sections/s1/reflections",
                "pathParameters": {"lessonId": "l1", "sectionId": "s1"},
            }
        },
        "body": "a",
    }
    add_authorizier_info(event, "e")

    learning_entries_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager, chatbot_wrapper)
    response = ret.handle(event)

    assert response["statusCode"] == 400


def test_learning_entries_api_handler_handle_put_reflection_3():
    """
    Handle proper input
    """
    reflection = {
        "userTopic": "Things to think",
        "userCode": "for i in range",
        "userExplanation": "goes around",
    }
    event = {
        "requestContext": {
            "http": {
                "method": "PUT",
                "path": "/lessons/l1/sections/s1/reflections",
                "pathParameters": {"lessonId": "l1", "sectionId": "s1"},
            }
        },
        "body": json.dumps(reflection),
    }
    add_authorizier_info(event, "e")

    learning_entries_table = Mock()
    learning_entries_table.save_item.return_value = ReflectionVersionItemModel(
        versionId="a",
        userId="e",
        lessonId="l1",
        sectionId="s1",
        userTopic="For loops",
        userCode="for i in range",
        userExplanation="round and round",
        createdAt="2025-05-25",
        isFinal=False,
    )
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    chatbot_wrapper.call_api.return_value = ChatBotFeedback("looks good", "mostly")
    ret = LearningEntriesApiHandler(learning_entries_table, secrets_manager, chatbot_wrapper)
    response = ret.handle(event)

    assert response["statusCode"] == 201
    body_dict = json.loads(response["body"])
    assert body_dict["aiFeedback"] == "looks good"
    assert body_dict["aiAssessment"] == "mostly"
