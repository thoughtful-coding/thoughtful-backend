#!/usr/bin/env python3
import json
from unittest.mock import Mock, patch

from aws_src_sample.utils.chatbot_utils import ChatBotWrapper


def test_chatbot_wrapper_init() -> None:
    ChatBotWrapper()


def test_chatbot_wrapper_gen_prompt() -> None:
    cbw = ChatBotWrapper()
    prompt = cbw.generate_chatbot_feedback_prompt(topic="For Loops", code="for i in range", explanation="Around")

    assert "**Topic:** For Loops" in prompt
    assert "```python\nfor i in range\n```" in prompt
    assert "**Student's Explanation:**\nAround\n" in prompt


@patch("aws_src_sample.utils.chatbot_utils.requests.post")
def test_call_api_normal_behavior(mock_post):
    mock_response = Mock()
    mock_response.status_code = 200

    expected_api_response_data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "Assessment: achieves\nFeedback: Your code is clear and the explanation is thorough."}
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
    feedback = cbw.call_api(chatbot_api_key="key", topic="For loops", code="for i in range(i):", explanation="Around")

    assert feedback.aiAssessment == "achieves"
    assert feedback.aiFeedback == "Your code is clear and the explanation is thorough."

    mock_post.assert_called_once()
