#!/usr/bin/env python3
from unittest.mock import Mock, patch

import pytest

from thoughtful_backend.utils.chatbot_utils import ChatBotApiError, ChatBotWrapper
from thoughtful_backend.utils.input_validator import SuspiciousInputError


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

    assert "**Student's Chosen Topic:** For Loops" in prompt
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

    assert "**Topic Student was Given to Reflect Upon:** For Loops" in prompt
    assert "**Code Student Was Given to Analyze:**" in prompt
    assert "```python\nfor i in range\n```" in prompt
    assert "**Student's Explanation:**\n\n```\nAround\n```" in prompt


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

    assert "**Topic Student was Given to Reflect Upon:** For Loops" in prompt
    assert "**Code Student Was Given to Analyze:**" in prompt
    assert "```python\nfor i in range\n```" in prompt
    assert "**Student's Explanation:**\n\n```\nAround\n```" in prompt
    assert "**Context of Where the Student Is/What They Know:**" in prompt
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

    assert "**Student's Chosen Topic:** While Loops" in prompt
    assert "```python\nwhile True: break\n```" in prompt
    assert "**Student's Explanation:**\n\nThis creates an infinite loop and breaks immediately\n" in prompt
    assert "**Context of Where the Student Is/What They Know:**" in prompt
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

    assert "**Student's Chosen Topic:** For Loops" in prompt
    assert "```python\nfor i in range\n```" in prompt
    assert "**Student's Explanation:**\n\nAround\n" in prompt
    # Extra context section should be present but empty
    assert "**Context of Where the Student Is/What They Know:**" in prompt


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

    assert feedback.aiPredictionAssessment == "mostly"
    assert feedback.aiExplanationAssessment == "developing"
    assert feedback.aiOverallComment == "I need more"

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


@patch("thoughtful_backend.utils.chatbot_utils.requests.post")
def test_output_validation_blocks_excessive_feedback(mock_post):
    """
    Test that output validation blocks AI responses exceeding MAX_FEEDBACK_LENGTH.
    """
    mock_response = Mock()
    mock_response.status_code = 200

    # Create feedback that exceeds the 500 char limit
    excessive_feedback = "This is feedback. " * 50  # ~900 chars

    expected_api_response_data = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": f'{{"aiFeedback": "{excessive_feedback}", "aiAssessment": "mostly"}}'}],
                    "role": "model",
                },
            }
        ],
    }
    mock_response.json.return_value = expected_api_response_data
    mock_post.return_value = mock_response

    cbw = ChatBotWrapper()

    with pytest.raises(ChatBotApiError, match="exceeds maximum length"):
        cbw.call_reflection_api(
            chatbot_api_key="key",
            topic="Loops",
            is_topic_predefined=False,
            code="for i in range(10): print(i)",
            is_code_predefined=False,
            explanation="This loops and prints numbers",
        )


@patch("thoughtful_backend.utils.chatbot_utils.requests.post")
def test_output_validation_allows_normal_feedback(mock_post):
    """
    Test that output validation allows normal-length feedback.
    """
    mock_response = Mock()
    mock_response.status_code = 200

    normal_feedback = "Good work! Your explanation is clear and demonstrates understanding of the concept."

    expected_api_response_data = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": f'{{"aiFeedback": "{normal_feedback}", "aiAssessment": "achieves"}}'}],
                    "role": "model",
                },
            }
        ],
    }
    mock_response.json.return_value = expected_api_response_data
    mock_post.return_value = mock_response

    cbw = ChatBotWrapper()

    # Should not raise
    result = cbw.call_reflection_api(
        chatbot_api_key="key",
        topic="Loops",
        is_topic_predefined=False,
        code="for i in range(10): print(i)",
        is_code_predefined=False,
        explanation="This loops and prints numbers",
    )

    assert result.aiFeedback == normal_feedback
    assert result.aiAssessment == "achieves"


def test_call_reflection_api_validates_input_excessive_length():
    """
    Test that call_reflection_api validates input and rejects overly long explanations.
    """
    cbw = ChatBotWrapper()

    with pytest.raises(SuspiciousInputError, match="exceeds maximum length"):
        cbw.call_reflection_api(
            chatbot_api_key="key",
            topic="Loops",
            is_topic_predefined=False,
            code="for i in range(10): print(i)",
            is_code_predefined=False,
            explanation="A" * 3000,  # Exceeds 2000 char limit
        )


def test_call_reflection_api_validates_input_excessive_headers():
    """
    Test that call_reflection_api validates input and rejects too many markdown headers.
    """
    cbw = ChatBotWrapper()

    with pytest.raises(SuspiciousInputError, match="too many section headers"):
        cbw.call_reflection_api(
            chatbot_api_key="key",
            topic="Loops",
            is_topic_predefined=False,
            code="for i in range(10): print(i)",
            is_code_predefined=False,
            explanation="### 1\n### 2\n### 3\n### 4\n### 5",  # Too many headers
        )


def test_call_reflection_api_validates_input_special_chars():
    """
    Test that call_reflection_api validates input and rejects excessive consecutive special characters.
    """
    cbw = ChatBotWrapper()

    with pytest.raises(SuspiciousInputError, match="unusual character sequences"):
        cbw.call_reflection_api(
            chatbot_api_key="key",
            topic="Loops",
            is_topic_predefined=False,
            code="for i in range(10): print(i)",
            is_code_predefined=False,
            explanation="This is @@@@@@@@@@@@@ suspicious",  # Too many consecutive special chars
        )


def test_call_primm_evaluation_api_validates_input_excessive_length():
    """
    Test that call_primm_evaluation_api validates input and rejects overly long predictions.
    """
    cbw = ChatBotWrapper()

    with pytest.raises(SuspiciousInputError, match="exceeds maximum length"):
        cbw.call_primm_evaluation_api(
            chatbot_api_key="key",
            code_snippet="print('hello')",
            prediction_prompt_text="What will this print?",
            user_prediction_text="A" * 1500,  # Exceeds 1000 char limit for predictions
            user_explanation_text="It prints hello",
            actual_output_summary="hello",
        )


def test_call_primm_evaluation_api_validates_input_excessive_headers():
    """
    Test that call_primm_evaluation_api validates input and rejects too many headers in explanation.
    """
    cbw = ChatBotWrapper()

    with pytest.raises(SuspiciousInputError, match="too many section headers"):
        cbw.call_primm_evaluation_api(
            chatbot_api_key="key",
            code_snippet="print('hello')",
            prediction_prompt_text="What will this print?",
            user_prediction_text="It will print hello",
            user_explanation_text="### 1\n### 2\n### 3\n### 4\n### 5",  # Too many headers
            actual_output_summary="hello",
        )
