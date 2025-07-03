#!/usr/bin/env python3
from unittest.mock import Mock, patch

import pytest

from aws_src_sample.utils.chatbot_utils import ChatBotWrapper


def test_chatbot_wrapper_init() -> None:
    ChatBotWrapper()


def test_chatbot_wrapper_gen_reflection_feedback_prompt_1() -> None:
    """
    Test prompt where student writes their own code
    """

    cbw = ChatBotWrapper()
    prompt = cbw.generate_reflection_feedback_prompt(
        topic="For Loops",
        is_topic_predefined=False,
        code="for i in range",
        is_code_predefined=False,
        explanation="Around",
    )

    assert "**Topic:** For Loops" in prompt
    assert "```python\nfor i in range\n```" in prompt
    assert "**Student's Explanation:**\n\nAround\n" in prompt


def test_chatbot_wrapper_gen_reflection_feedback_prompt_2() -> None:
    """
    Test prompt where student is given predefined code they have to explain
    """

    cbw = ChatBotWrapper()
    prompt = cbw.generate_reflection_feedback_prompt(
        topic="For Loops",
        is_topic_predefined=False,
        code="for i in range",
        is_code_predefined=True,
        explanation="Around",
    )

    assert "**Topic of Student's Analysis:** For Loops" in prompt
    assert "**Code Student Was Given to Analyze:**" in prompt
    assert "```python\nfor i in range\n```" in prompt
    assert "**Student's Explanation:**\n\nAround\n" in prompt


@patch("aws_src_sample.utils.chatbot_utils.requests.post")
def test_call_reflection_feedback_api_normal_behavior(mock_post):
    mock_response = Mock()
    mock_response.status_code = 200

    expected_api_response_data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": '{"aiAssessment": "achieves", "aiFeedback": "Your code is clear and the explanation is thorough."}'
                        }
                    ],
                    "role": "model",
                },
            }
        ],
    }
    mock_response.json.return_value = expected_api_response_data
    mock_post.return_value = mock_response

    cbw = ChatBotWrapper()

    # Expected prompt that will be generated
    feedback = cbw.call_reflection_api(
        chatbot_api_key="key",
        topic="For loops",
        is_topic_predefined=False,
        code="for i in range(i):",
        is_code_predefined=False,
        explanation="Around",
    )

    assert feedback.aiAssessment == "achieves"
    assert feedback.aiFeedback == "Your code is clear and the explanation is thorough."

    mock_post.assert_called_once()


@pytest.mark.xfail(raises=ValueError)
@patch("aws_src_sample.utils.chatbot_utils.requests.post")
def test_call_reflection_feedback_api_abnormal_behavior(mock_post):
    mock_response = Mock()
    mock_response.status_code = 200

    expected_api_response_data = {
        "candidates": [
            {
                "content": {"parts": []},
            }
        ],
    }
    mock_response.json.return_value = expected_api_response_data
    mock_post.return_value = mock_response

    cbw = ChatBotWrapper()

    # Expected prompt that will be generated
    cbw.call_reflection_api(
        chatbot_api_key="key",
        topic="For loops",
        is_topic_predefined=False,
        code="for i in range(i):",
        is_code_predefined=False,
        explanation="Around",
    )


def test_chatbot_wrapper_gen_primm_feedback_prompt() -> None:
    cbw = ChatBotWrapper()
    prompt = cbw.generate_primm_feedback_prompt(
        code_snippet="for i in range(4)",
        prediction_prompt_text="What's it do?",
        user_prediction_text="it loops",
        user_prediction_confidence=3,
        user_explanation_text="i was right",
        actual_output_summary="it went around",
    )

    assert "**Student's Confidence:** High" in prompt
    assert "```python\nfor i in range(4)\n```" in prompt


@patch("aws_src_sample.utils.chatbot_utils.requests.post")
def test_call_primm_feedback_api_normal_behavior(mock_post):
    mock_response = Mock()
    mock_response.status_code = 200

    expected_api_response_data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": '{"aiPredictionAssessment": "mostly", "aiExplanationAssessment": "developing", "aiOverallComment": "I need more"}'
                        }
                    ],
                    "role": "model",
                },
            }
        ],
    }
    mock_response.json.return_value = expected_api_response_data
    mock_post.return_value = mock_response

    cbw = ChatBotWrapper()

    # Expected prompt that will be generated
    feedback = cbw.call_primm_evaluation_api(
        chatbot_api_key="key",
        code_snippet="for i in range(4):",
        prediction_prompt_text="What's it do?",
        user_prediction_text="it loops",
        user_prediction_confidence=3,
        user_explanation_text="I was right",
        actual_output_summary="it went around",
    )

    assert feedback.ai_prediction_assessment == "mostly"
    assert feedback.ai_explanation_assessment == "developing"
    assert feedback.ai_overall_comment == "I need more"

    mock_post.assert_called_once()


@pytest.mark.xfail(raises=ValueError)
@patch("aws_src_sample.utils.chatbot_utils.requests.post")
def test_call_primm_feedback_api_abnormal_behavior(mock_post):
    mock_response = Mock()
    mock_response.status_code = 200

    expected_api_response_data = {
        "candidates": [
            {
                "content": {
                    "parts": [],
                    "role": "model",
                },
            }
        ],
    }
    mock_response.json.return_value = expected_api_response_data
    mock_post.return_value = mock_response

    cbw = ChatBotWrapper()

    # Expected prompt that will be generated
    cbw.call_primm_evaluation_api(
        chatbot_api_key="key",
        code_snippet="for i in range(4):",
        prediction_prompt_text="What's it do?",
        user_prediction_text="it loops",
        user_prediction_confidence=3,
        user_explanation_text="I was right",
        actual_output_summary="it went around",
    )
