#!/usr/bin/env python3
import json
from unittest.mock import MagicMock, Mock

from aws_src_sample.lambdas.learning_entries_lambda import LearningEntriesApiHandler
from aws_src_sample.models.learning_entry_models import ReflectionVersionItemModel
from aws_src_sample.utils.chatbot_utils import ChatBotFeedback


def add_authorizer_info(event: dict, user_id: str) -> None:
    assert "authorizer" not in event["requestContext"]
    event["requestContext"]["authorizer"] = {"jwt": {"claims": {"email": user_id}}}


def test_learning_entries_api_handler_1():
    learning_entries_table = Mock()
    throttle_table = Mock()
    secrets_repo = Mock()
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, throttle_table, secrets_repo, chatbot_wrapper)
    assert ret.learning_entries_table == learning_entries_table
    assert ret.throttle_table == throttle_table
    assert ret.secrets_repo == secrets_repo
    assert ret.chatbot_wrapper == chatbot_wrapper


def test_learning_entries_api_handler_handle_error_1():
    """
    Unidentified user -> "User identification failed"
    """
    event = {}

    learning_entries_table = Mock()
    throttle_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, throttle_table, secrets_manager, chatbot_wrapper)
    response = ret.handle(event)

    assert response["statusCode"] == 401


def test_learning_entries_api_handler_handle_error_2():
    """
    Improper/unhandled method -> "HTTP method not allow"
    """
    event = {"requestContext": {}}
    add_authorizer_info(event, "e")

    learning_entries_table = Mock()
    throttle_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, throttle_table, secrets_manager, chatbot_wrapper)
    response = ret.handle(event)

    assert response["statusCode"] == 405


def test_learning_entries_api_handler_handle_get_reflections_1():
    event = {
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/reflections/l1/sections/s1",
            }
        },
        "pathParameters": {"lessonId": "l1", "sectionId": "s1"},
    }
    add_authorizer_info(event, "e")

    learning_entries_table = Mock()
    learning_entries_table.get_versions_for_section.return_value = ([], None)
    throttle_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, throttle_table, secrets_manager, chatbot_wrapper)
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_list = json.loads(response["body"])
    assert body_list == {"versions": []}


def test_learning_entries_api_handler_handle_get_reflection_2():
    event = {
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/reflections/l1/sections/s1",
            }
        },
        "pathParameters": {"lessonId": "l1", "sectionId": "s1"},
        "queryStringParameters": {"limit": "10", "lastEvaluatedKey": "{}"},
    }
    add_authorizer_info(event, "e")

    learning_entries_table = Mock()
    learning_entries_table.get_versions_for_section.return_value = ([], None)
    throttle_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, throttle_table, secrets_manager, chatbot_wrapper)
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_list = json.loads(response["body"])
    assert body_list == {"versions": []}


def test_learning_entries_api_handler_handle_get_reflection_3():
    event = {
        "version": "2.0",
        "routeKey": "GET /reflections/{lessonId}/sections/{sectionId}",
        "rawPath": "/reflections/FIXME/sections/python-reflection",
        "rawQueryString": "hey=there",
        "headers": {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9",
            "authorization": "Bearer ..-----",
            "content-length": "0",
            "content-type": "application/json",
            "host": "123456.execute-api.us-east-2.amazonaws.com",
            "origin": "http://localhost:5173",
            "priority": "u=1, i",
            "referer": "http://localhost:5173/",
            "sec-ch-ua": '"Chromium"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "user-agent": "Mozilla/5.0",
            "x-amzn-trace-id": "Root=1-blah",
            "x-forwarded-for": "127.0.0.1",
            "x-forwarded-port": "443",
            "x-forwarded-proto": "https",
        },
        "queryStringParameters": {"hey": "there"},
        "requestContext": {
            "accountId": "abc1234",
            "apiId": "123456",
            "authorizer": {
                "jwt": {
                    "claims": {
                        "email": "erizzi@ucls.uchicago.edu",
                        "email_verified": "true",
                    },
                    "scopes": None,
                }
            },
            "domainName": "123456.execute-api.us-east-2.amazonaws.com",
            "domainPrefix": "123456",
            "http": {
                "method": "GET",
                "path": "/reflections/FIXME/sections/python-reflection",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "Mozilla/5.0",
            },
            "requestId": "LMF",
            "routeKey": "GET /reflections/{lessonId}/sections/{sectionId}",
            "stage": "$default",
            "time": "26/May/2025:18:45:31 +0000",
            "timeEpoch": 1748285131734,
        },
        "pathParameters": {"lessonId": "FIXME", "sectionId": "python-reflection"},
        "isBase64Encoded": False,
    }

    learning_entries_table = Mock()
    learning_entries_table.get_versions_for_section.return_value = ([], None)
    throttle_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, throttle_table, secrets_manager, chatbot_wrapper)
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
    add_authorizer_info(event, "e")

    learning_entries_table = Mock()
    learning_entries_table.get_finalized_entries_for_user.return_value = ([], None)
    throttle_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, throttle_table, secrets_manager, chatbot_wrapper)
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
    add_authorizer_info(event, "e")

    learning_entries_table = Mock()
    learning_entries_table.get_finalized_entries_for_user.return_value = ([], None)
    throttle_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, throttle_table, secrets_manager, chatbot_wrapper)
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_list = json.loads(response["body"])
    assert body_list == {"entries": []}


def test_learning_entries_api_handler_handle_post_reflection_1():
    """
    Handle missing body
    """
    event = {
        "requestContext": {
            "http": {
                "method": "POST",
                "path": "/reflections/l1/sections/s1",
            }
        },
        "pathParameters": {"lessonId": "l1", "sectionId": "s1"},
    }
    add_authorizer_info(event, "e")

    learning_entries_table = Mock()
    throttle_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, throttle_table, secrets_manager, chatbot_wrapper)
    response = ret.handle(event)

    assert response["statusCode"] == 400


def test_learning_entries_api_handler_handle_post_reflection_2():
    """
    Handle bad body
    """
    event = {
        "requestContext": {
            "http": {
                "method": "POST",
                "path": "/reflections/l1/sections/s1",
            }
        },
        "pathParameters": {"lessonId": "l1", "sectionId": "s1"},
        "body": "a",
    }
    add_authorizer_info(event, "e")

    learning_entries_table = Mock()
    throttle_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    ret = LearningEntriesApiHandler(learning_entries_table, throttle_table, secrets_manager, chatbot_wrapper)
    response = ret.handle(event)

    assert response["statusCode"] == 400


def test_learning_entries_api_handler_handle_post_reflection_3():
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
                "method": "POST",
                "path": "/reflections/l1/sections/s1",
            }
        },
        "pathParameters": {"lessonId": "l1", "sectionId": "s1"},
        "body": json.dumps(reflection),
    }
    add_authorizer_info(event, "e")

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
        aiFeedback="looks good",
        aiAssessment="mostly",
        isFinal=False,
    )
    throttle_table = Mock()
    mock_context_manager = MagicMock()
    mock_context_manager.__enter__.return_value = None
    mock_context_manager.__exit__.return_value = None
    throttle_table.throttle_action.return_value = mock_context_manager

    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    chatbot_wrapper.call_reflection_api.return_value = ChatBotFeedback("looks good", "mostly")
    ret = LearningEntriesApiHandler(learning_entries_table, throttle_table, secrets_manager, chatbot_wrapper)
    response = ret.handle(event)

    assert response["statusCode"] == 201
    body_dict = json.loads(response["body"])
    assert body_dict["aiFeedback"] == "looks good"
    assert body_dict["aiAssessment"] == "mostly"
