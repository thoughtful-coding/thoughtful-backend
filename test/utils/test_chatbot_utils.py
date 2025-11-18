#!/usr/bin/env python3
from unittest.mock import Mock, patch

import pytest

from thoughtful_backend.utils.chatbot_utils import ChatBotApiError, ChatBotWrapper


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


@patch("thoughtful_backend.utils.chatbot_utils.requests.post")
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


@pytest.mark.xfail(raises=ChatBotApiError)
@patch("thoughtful_backend.utils.chatbot_utils.requests.post")
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


def test_chatbot_wrapper_gen_reflection_feedback_prompt_with_extra_context_predefined() -> None:
    """
    Test prompt with extra context where student is given predefined code
    """
    cbw = ChatBotWrapper()
    prompt = cbw.generate_reflection_feedback_prompt(
        topic="For Loops",
        is_topic_predefined=False,
        code="for i in range",
        is_code_predefined=True,
        explanation="Around",
        extra_context="Focus on code efficiency and time complexity.",
    )

    assert "**Topic of Student's Analysis:** For Loops" in prompt
    assert "**Code Student Was Given to Analyze:**" in prompt
    assert "```python\nfor i in range\n```" in prompt
    assert "**Student's Explanation:**\n\nAround\n" in prompt
    assert "### Additional Context for Evaluation" in prompt
    assert "Focus on code efficiency and time complexity." in prompt


def test_chatbot_wrapper_gen_reflection_feedback_prompt_with_extra_context_student_code() -> None:
    """
    Test prompt with extra context where student writes their own code
    """
    cbw = ChatBotWrapper()
    prompt = cbw.generate_reflection_feedback_prompt(
        topic="While Loops",
        is_topic_predefined=False,
        code="while True: break",
        is_code_predefined=False,
        explanation="This creates an infinite loop and breaks immediately",
        extra_context="Pay special attention to edge cases and readability.",
    )

    assert "**Topic:** While Loops" in prompt
    assert "```python\nwhile True: break\n```" in prompt
    assert "**Student's Explanation:**\n\nThis creates an infinite loop and breaks immediately\n" in prompt
    assert "### Additional Context for Evaluation" in prompt
    assert "Pay special attention to edge cases and readability." in prompt


def test_chatbot_wrapper_gen_reflection_feedback_prompt_without_extra_context() -> None:
    """
    Test that prompts work correctly when extra_context is not provided (backward compatibility)
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
    # Should not contain extra context section
    assert "### Additional Context for Evaluation" not in prompt


def test_chatbot_wrapper_gen_primm_feedback_prompt() -> None:
    cbw = ChatBotWrapper()
    prompt = cbw.generate_primm_feedback_prompt(
        code_snippet="for i in range(4)",
        prediction_prompt_text="What's it do?",
        user_prediction_text="it loops",
        user_explanation_text="i was right",
        actual_output_summary="it went around",
    )

    assert "```python\nfor i in range(4)\n```" in prompt


@patch("thoughtful_backend.utils.chatbot_utils.requests.post")
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
        user_explanation_text="I was right",
        actual_output_summary="it went around",
    )

    assert feedback.ai_prediction_assessment == "mostly"
    assert feedback.ai_explanation_assessment == "developing"
    assert feedback.ai_overall_comment == "I need more"

    mock_post.assert_called_once()


@pytest.mark.xfail(raises=ChatBotApiError)
@patch("thoughtful_backend.utils.chatbot_utils.requests.post")
def test_call_primm_feedback_api_abnormal_behavior(mock_post):
    """
    Test that if feedback is missing, we generate a ChatBot error
    """
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
        user_explanation_text="I was right",
        actual_output_summary="it went around",
    )
