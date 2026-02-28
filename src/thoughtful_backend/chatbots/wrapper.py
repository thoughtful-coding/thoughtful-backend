"""
ChatBotWrapper - unified interface for AI-powered feedback on student submissions.
"""

import logging
import typing
from typing import Literal

import pydantic

from thoughtful_backend.chatbots.claude import ClaudeApiError, call_claude_api
from thoughtful_backend.chatbots.gemini import GeminiApiError, call_gemini_api
from thoughtful_backend.chatbots.prompts import (
    PREDEFINED_CODE_REFLECTION_PROMPT,
    PRIMM_EVALUATION_PROMPT,
    STUDENT_CODE_REFLECTION_PROMPT,
)
from thoughtful_backend.models.learning_entry_models import ChatBotFeedback
from thoughtful_backend.models.primm_feedback_models import PrimmEvaluationResponseModel
from thoughtful_backend.utils.input_validator import InputValidator

_LOGGER = logging.getLogger(__name__)

ChatBotProvider = Literal["gemini", "claude"]


class ChatBotApiError(Exception):
    """Unified error class for chatbot API failures."""

    def __init__(self, msg: str, status_code: int = 503) -> None:
        super().__init__(msg)
        self.status_code = status_code


class ChatBotWrapper:
    """
    Unified wrapper for AI-powered feedback generation.
    Supports multiple providers (Gemini, Claude) with a consistent interface.
    """

    MAX_FEEDBACK_LENGTH = 500

    def __init__(self, provider: ChatBotProvider, api_key: str) -> None:
        self.provider = provider
        self._api_key = api_key

    @classmethod
    def _validate_output_length(cls, text: str, field_name: str) -> None:
        """
        Validates that AI-generated output doesn't exceed safe limits.
        Prevents AI from being manipulated into generating excessive content.
        """
        if len(text) > cls.MAX_FEEDBACK_LENGTH:
            _LOGGER.error(f"AI output too long: {field_name} is {len(text)} chars (max {cls.MAX_FEEDBACK_LENGTH})")
            raise ChatBotApiError(
                f"AI response validation failed: {field_name} exceeds maximum length", status_code=500
            )

    def _call_api(self, *, prompt: str, timeout_seconds: int = 45) -> dict:
        """
        Dispatch to the appropriate provider API.
        """
        try:
            if self.provider == "gemini":
                return call_gemini_api(api_key=self._api_key, prompt=prompt, timeout_seconds=timeout_seconds)
            else:
                return call_claude_api(api_key=self._api_key, prompt=prompt, timeout_seconds=timeout_seconds)
        except (GeminiApiError, ClaudeApiError) as e:
            raise ChatBotApiError(str(e), e.status_code)

    def generate_reflection_feedback_prompt(
        self,
        *,
        topic: str,
        is_topic_predefined: bool,
        code: str,
        is_code_predefined: bool,
        explanation: str,
        extra_context: typing.Optional[str] = None,
    ) -> str:
        """
        Generates the formatted prompt for reflection feedback evaluation.
        Selects appropriate template based on whether code is predefined or student-created.
        """
        extra_context_section = ""
        if extra_context:
            extra_context_section = f"### Additional Context for Evaluation\n\n{extra_context}"

        if is_code_predefined:
            return PREDEFINED_CODE_REFLECTION_PROMPT.format(
                topic=topic, code=code, explanation=explanation, extra_context_section=extra_context_section
            )
        else:
            return STUDENT_CODE_REFLECTION_PROMPT.format(
                topic=topic, code=code, explanation=explanation, extra_context_section=extra_context_section
            )

    def call_reflection_api(
        self,
        *,
        topic: str,
        is_topic_predefined: bool,
        code: str,
        is_code_predefined: bool,
        explanation: str,
        extra_context: typing.Optional[str] = None,
    ) -> ChatBotFeedback:
        """
        Calls the AI API to generate feedback on a student's reflection submission.
        Validates input before calling API and validates output length to prevent manipulation.

        :param topic: The topic being analyzed
        :param is_topic_predefined: Whether the topic was provided or student-chosen
        :param code: The Python code being analyzed
        :param is_code_predefined: Whether code was provided or student-written
        :param explanation: Student's explanation of the code
        :param extra_context: Optional instructor-provided evaluation context
        :return: ChatBotFeedback containing AI-generated feedback and assessment
        :raises SuspiciousInputError: If input validation fails
        :raises ValueError: If response structure is invalid
        :raises ChatBotApiError: If API call fails or output validation fails
        """
        InputValidator.validate_reflection_input(
            topic=topic,
            code=code,
            explanation=explanation,
            extra_context=extra_context,
        )

        prompt = self.generate_reflection_feedback_prompt(
            topic=topic,
            is_topic_predefined=is_topic_predefined,
            code=code,
            is_code_predefined=is_code_predefined,
            explanation=explanation,
            extra_context=extra_context,
        )
        generated_dict = self._call_api(prompt=prompt, timeout_seconds=45)

        try:
            feedback = ChatBotFeedback(**generated_dict)
            self._validate_output_length(feedback.aiFeedback, "aiFeedback")
            return feedback
        except ValueError as e:
            _LOGGER.error(f"Error parsing API response: {e}. Raw data: {generated_dict}", exc_info=True)
            raise ValueError(f"Invalid or unexpected response structure from AI for reflection: {str(e)}")

    def generate_primm_feedback_prompt(
        self,
        *,
        code_snippet: str,
        prediction_prompt_text: str,
        user_prediction_text: str,
        user_explanation_text: str,
        actual_output_summary: typing.Optional[str],
    ) -> str:
        """
        Generates the formatted prompt for PRIMM activity evaluation.
        """
        return PRIMM_EVALUATION_PROMPT.format(
            code_snippet=code_snippet,
            prediction_prompt_text=prediction_prompt_text,
            user_prediction_text=user_prediction_text,
            user_explanation_text=user_explanation_text,
            actual_output_summary=actual_output_summary or "Not provided.",
        )

    def call_primm_evaluation_api(
        self,
        *,
        code_snippet: str,
        prediction_prompt_text: str,
        user_prediction_text: str,
        user_explanation_text: str,
        actual_output_summary: typing.Optional[str],
    ) -> PrimmEvaluationResponseModel:
        """
        Calls the AI API to evaluate a student's PRIMM activity submission.
        Validates input before calling API and validates output length to prevent manipulation.

        :param code_snippet: The Python code snippet to evaluate
        :param prediction_prompt_text: The prediction question/prompt
        :param user_prediction_text: Student's prediction of code output
        :param user_explanation_text: Student's explanation of how code works
        :param actual_output_summary: Summary of actual code execution output
        :return: PrimmEvaluationResponseModel containing AI-generated feedback
        :raises SuspiciousInputError: If input validation fails
        :raises ValueError: If response structure is invalid
        :raises ChatBotApiError: If API call fails or output validation fails
        """
        InputValidator.validate_primm_input(
            code_snippet=code_snippet,
            user_prediction_text=user_prediction_text,
            user_explanation_text=user_explanation_text,
            prediction_prompt_text=prediction_prompt_text,
            actual_output_summary=actual_output_summary,
        )

        prompt = self.generate_primm_feedback_prompt(
            code_snippet=code_snippet,
            prediction_prompt_text=prediction_prompt_text,
            user_prediction_text=user_prediction_text,
            user_explanation_text=user_explanation_text,
            actual_output_summary=actual_output_summary,
        )
        generated_dict = self._call_api(prompt=prompt, timeout_seconds=60)

        try:
            response = PrimmEvaluationResponseModel.model_validate(generated_dict)
            _LOGGER.info(f"Parsed: {response.model_dump_json(indent=2, exclude_none=True)}")
            self._validate_output_length(response.aiOverallComment, "aiOverallComment")
            return response
        except (pydantic.ValidationError, ValueError) as e:
            _LOGGER.error(f"Error parsing API response: {e}. Raw data: {generated_dict}", exc_info=True)
            raise ValueError(f"Invalid or unexpected response structure from AI for PRIMM: {str(e)}")


# Quick integration test
# Usage: CLAUDE_API_KEY=xxx PYTHONPATH=$(pwd)/src python3 -m thoughtful_backend.chatbots.wrapper
#    or: GEMINI_API_KEY=xxx PYTHONPATH=$(pwd)/src python3 -m thoughtful_backend.chatbots.wrapper
if __name__ == "__main__":
    import os

    claude_key = os.environ.get("CLAUDE_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if claude_key:
        provider, api_key = "claude", claude_key
    elif gemini_key:
        provider, api_key = "gemini", gemini_key
    else:
        print("Set CLAUDE_API_KEY or GEMINI_API_KEY")
        exit(1)

    print(f"Testing {provider}...")
    wrapper = ChatBotWrapper(provider=provider, api_key=api_key)
    result = wrapper.call_reflection_api(
        topic="For loops",
        is_topic_predefined=False,
        code="for i in range(3):\n    print(i)",
        is_code_predefined=False,
        explanation="This loops 3 times and prints 0, 1, 2.",
    )
    print(f"aiFeedback: {result.aiFeedback}")
    print(f"aiAssessment: {result.aiAssessment}")
