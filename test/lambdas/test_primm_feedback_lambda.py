#!/usr/bin/env python3
import json
from unittest.mock import MagicMock, Mock

from aws_src_sample.lambdas.primm_feedback_lambda import PrimmFeedbackApiHandler
from aws_src_sample.models.primm_feedback_models import PrimmEvaluationResponseModel
from aws_src_sample.utils.chatbot_utils import ChatBotFeedback


def add_authorizier_info(event: dict, user_id: str) -> None:
    assert "authorizer" not in event["requestContext"]
    event["requestContext"]["authorizer"] = {"jwt": {"claims": {"email": user_id}}}


def test_primm_feedbackg_api_handler_1():
    throttle_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    primm_submissions_table = Mock()
    ret = PrimmFeedbackApiHandler(throttle_table, secrets_manager, chatbot_wrapper, primm_submissions_table)
    assert ret.throttle_table == throttle_table
    assert ret.chatbot_secrets_manager == secrets_manager
    assert ret.chatbot_wrapper == chatbot_wrapper


def test_primm_feedbackg_api_handler_handle_error_1():
    """
    Unidentified user -> "User identification failed"
    """
    event = {}

    throttle_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    primm_submissions_table = Mock()
    ret = PrimmFeedbackApiHandler(throttle_table, secrets_manager, chatbot_wrapper, primm_submissions_table)
    response = ret.handle(event)

    assert response["statusCode"] == 401


def test_primm_feedbackg_api_handler_handle_error_2():
    """
    Improper/unhandled method -> "HTTP method not allow"
    """
    event = {"requestContext": {}}
    add_authorizier_info(event, "e")

    throttle_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    primm_submissions_table = Mock()
    ret = PrimmFeedbackApiHandler(throttle_table, secrets_manager, chatbot_wrapper, primm_submissions_table)
    response = ret.handle(event)

    assert response["statusCode"] == 405


def test_primm_feedbackg_api_handler_handle_post_reflection_1():
    """
    Handle missing body
    """
    event = {
        "requestContext": {
            "http": {
                "method": "POST",
                "path": "/primm-feedback",
            }
        },
    }
    add_authorizier_info(event, "e")

    throttle_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    primm_submissions_table = Mock()
    ret = PrimmFeedbackApiHandler(throttle_table, secrets_manager, chatbot_wrapper, primm_submissions_table)
    response = ret.handle(event)

    assert response["statusCode"] == 400


def test_primm_feedbackg_api_handler_handle_post_reflection_2():
    """
    Handle bad body
    """
    event = {
        "requestContext": {
            "http": {
                "method": "POST",
                "path": "/primm-feedback",
            }
        },
        "body": "a",
    }
    add_authorizier_info(event, "e")

    throttle_table = Mock()
    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    primm_submissions_table = Mock()
    ret = PrimmFeedbackApiHandler(throttle_table, secrets_manager, chatbot_wrapper, primm_submissions_table)
    response = ret.handle(event)

    assert response["statusCode"] == 400


def test_primm_feedbackg_api_handler_handle_post_reflection_3():
    """
    Handle proper input
    """
    primm_eval = {
        "lesson_id": "li",
        "section_id": "s1",
        "primm_example_id": "not sure",
        "code_snippet": "for i in range",
        "user_prediction_prompt_text": "what's it do?",
        "user_prediction_text": "it loops",
        "user_prediction_confidence": 3,
        "user_explanation_text": "I was right",
    }
    event = {
        "requestContext": {
            "http": {
                "method": "POST",
                "path": "/primm-feedback",
            }
        },
        "body": json.dumps(primm_eval),
    }
    add_authorizier_info(event, "e")

    throttle_table = Mock()
    mock_context_manager = MagicMock()
    mock_context_manager.__enter__.return_value = None
    mock_context_manager.__exit__.return_value = None
    throttle_table.throttle_action.return_value = mock_context_manager

    secrets_manager = Mock()
    chatbot_wrapper = Mock()
    primm_submissions_table = Mock()

    chatbot_wrapper.call_primm_evaluation_api.return_value = PrimmEvaluationResponseModel(
        aiPredictionAssessment="developing",
        aiExplanationAssessment="mostly",
        aiOverallComment="more work to do",
    )
    ret = PrimmFeedbackApiHandler(throttle_table, secrets_manager, chatbot_wrapper, primm_submissions_table)
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_dict = json.loads(response["body"])
    assert body_dict["aiPredictionAssessment"] == "developing"
    assert body_dict["aiExplanationAssessment"] == "mostly"
    assert body_dict["aiOverallComment"] == "more work to do"
