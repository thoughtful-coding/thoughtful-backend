#!/usr/bin/env python3
import json
from unittest.mock import MagicMock, Mock

from thoughtful_backend.lambdas.primm_feedback_lambda import PrimmFeedbackApiHandler
from thoughtful_backend.models.primm_feedback_models import PrimmEvaluationResponseModel

from ..test_utils.authorizer import add_authorizer_info


def create_primm_feedback_api_handler(
    throttle_table=Mock(),
    secrets_table=Mock(),
    chatbot_wrapper=Mock(),
    primm_submissions_table=Mock(),
    metrics_manager=Mock(),
) -> PrimmFeedbackApiHandler:

    ret = PrimmFeedbackApiHandler(
        throttle_table,
        secrets_table,
        chatbot_wrapper,
        primm_submissions_table,
        metrics_manager=metrics_manager,
    )
    assert ret.throttle_table == throttle_table
    assert ret.secrets_table == secrets_table
    assert ret.chatbot_wrapper == chatbot_wrapper
    assert ret.primm_submissions_table == primm_submissions_table
    assert ret.metrics_manager == metrics_manager

    return ret


def test_primm_feedbackg_api_handler_1():
    create_primm_feedback_api_handler()


def test_primm_feedbackg_api_handler_handle_error_1():
    """
    Unidentified user -> "User identification failed"
    """
    event = {}

    ret = create_primm_feedback_api_handler()
    response = ret.handle(event)

    assert response["statusCode"] == 401


def test_primm_feedbackg_api_handler_handle_error_2():
    """
    Improper/unhandled method -> "HTTP method not allow"
    """
    event = {"requestContext": {}}
    add_authorizer_info(event, "e")

    ret = create_primm_feedback_api_handler()
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
    add_authorizer_info(event, "e")

    ret = create_primm_feedback_api_handler()
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
    add_authorizer_info(event, "e")

    ret = create_primm_feedback_api_handler()
    response = ret.handle(event)

    assert response["statusCode"] == 400


def test_primm_feedbackg_api_handler_handle_post_reflection_3():
    """
    Handle proper input
    """
    primm_eval = {
        "lessonId": "li",
        "sectionId": "s1",
        "primmExampleId": "not sure",
        "codeSnippet": "for i in range",
        "userPredictionPromptText": "what's it do?",
        "userPredictionText": "it loops",
        "userExplanationText": "I was right",
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
    add_authorizer_info(event, "e")

    throttle_table = Mock()
    mock_context_manager = MagicMock()
    mock_context_manager.__enter__.return_value = None
    mock_context_manager.__exit__.return_value = None
    throttle_table.throttle_action.return_value = mock_context_manager

    chatbot_wrapper = Mock()
    chatbot_wrapper.call_primm_evaluation_api.return_value = PrimmEvaluationResponseModel(
        aiPredictionAssessment="developing",
        aiExplanationAssessment="mostly",
        aiOverallComment="more work to do",
    )
    ret = create_primm_feedback_api_handler(throttle_table=throttle_table, chatbot_wrapper=chatbot_wrapper)
    response = ret.handle(event)

    assert response["statusCode"] == 200
    body_dict = json.loads(response["body"])
    assert body_dict["aiPredictionAssessment"] == "developing"
    assert body_dict["aiExplanationAssessment"] == "mostly"
    assert body_dict["aiOverallComment"] == "more work to do"
