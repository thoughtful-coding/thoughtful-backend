#!/usr/bin/env python3
import json
import os
from unittest.mock import Mock

from aws_src_sample.dynamodb.user_progress_table import UserProgressModel
from aws_src_sample.lambdas.user_progress_lambda import UserProgressApiHandler


def add_authorizier_info(event: dict, user_id: str) -> None:
    assert "authorizer" not in event["requestContext"]
    event["requestContext"]["authorizer"] = {"jwt": {"claims": {"email": user_id}}}


def test_user_progress_api_handler_1():
    ret = UserProgressApiHandler("1")
    assert ret.user_progress_table == "1"


def test_user_progress_api_handler_handle_error_1():
    """
    Unidentified user -> "User identification failed"
    """
    event = {}

    user_progress_table = Mock()
    ret = UserProgressApiHandler(user_progress_table)
    response = ret.handle(event)

    assert response["statusCode"] == 401


def test_user_progress_api_handler_handle_error_2():
    """
    Improper/unhandled method -> "HTTP method not allow"
    """
    event = {"requestContext": {}}
    add_authorizier_info(event, "e")

    user_progress_table = Mock()
    ret = UserProgressApiHandler(user_progress_table)
    response = ret.handle(event)

    assert response["statusCode"] == 405


def test_user_progress_api_handler_handle_get_1():
    event = {"requestContext": {"http": {"method": "GET"}}}
    add_authorizier_info(event, "e")

    user_progress_table = Mock()
    user_progress_table.get_progress.return_value = None
    ret = UserProgressApiHandler(user_progress_table)
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_dict = json.loads(response["body"])
    assert body_dict["userId"] == "e"
    assert body_dict["completion"] == {}


def test_user_progress_api_handler_handle_get_2():
    event = {"requestContext": {"http": {"method": "GET"}}}
    add_authorizier_info(event, "e")

    user_progress_table = Mock()
    user_progress_table.get_progress.return_value = UserProgressModel(userId="l", completion={"m": {}})
    ret = UserProgressApiHandler(user_progress_table)
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_dict = json.loads(response["body"])
    assert body_dict["userId"] == "l"
    assert body_dict["completion"] == {"m": {}}


def test_user_progress_api_handler_handle_put_1():
    """
    Handle missing body
    """
    event = {"requestContext": {"http": {"method": "PUT"}}}
    add_authorizier_info(event, "e")

    user_progress_table = Mock()
    ret = UserProgressApiHandler(user_progress_table)
    response = ret.handle(event)

    assert response["statusCode"] == 400
    assert response["body"] == '{"message": "Missing request body."}'


def test_user_progress_api_handler_handle_put_2():
    """
    Handle bad body
    """
    event = {"requestContext": {"http": {"method": "PUT"}}, "body": "a"}
    add_authorizier_info(event, "e")

    user_progress_table = Mock()
    ret = UserProgressApiHandler(user_progress_table)
    response = ret.handle(event)

    assert response["statusCode"] == 400
    assert response["body"] == '{"message": "Invalid JSON format in request body."}'


def test_user_progress_api_handler_handle_put_3():
    """
    Handle proper input
    """
    event = {
        "requestContext": {"http": {"method": "PUT"}},
        "body": '{"completions": [{"lessonId": "1", "sectionId": "a"}]}',
    }
    add_authorizier_info(event, "e")

    user_progress_table = Mock()
    user_progress_table.update_progress.return_value = UserProgressModel(userId="l", completion={"m": {}})
    ret = UserProgressApiHandler(user_progress_table)
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_dict = json.loads(response["body"])
    assert body_dict["userId"] == "l"
    assert body_dict["completion"] == {"m": {}}
