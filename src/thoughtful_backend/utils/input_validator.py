import logging
from typing import Optional

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class SuspiciousInputError(ValueError):
    pass


class InputValidator:
    """
    Validates user input using objective, measurable criteria.

    Protection mechanisms:
    - Length limits per field type
    - Control character restrictions
    - Excessive formatting limits
    - Character composition checks
    """

    # Maximum lengths for different input types
    MAX_LENGTHS = {
        "topic": 200,
        "code": 5000,
        "explanation": 2000,
        "extra_context": 1000,
        "prediction": 1000,
        "output_summary": 500,
    }

    # Maximum number of markdown headers (prevents section injection)
    MAX_MARKDOWN_HEADERS = 3

    # Maximum number of code block markers in non-code fields
    MAX_CODE_BLOCKS = 2

    # Maximum percentage of non-printable/control characters
    MAX_CONTROL_CHAR_PERCENTAGE = 5

    # Maximum consecutive special characters
    MAX_CONSECUTIVE_SPECIAL_CHARS = 10

    @classmethod
    def validate_reflection_input(
        cls,
        topic: str,
        code: str,
        explanation: str,
        extra_context: Optional[str] = None,
    ) -> None:
        """
        Validate all fields in a reflection submission.

        :raises SuspiciousInputError: If input validation fails
        """
        cls.validate_field(topic, "topic")
        cls.validate_field(code, "code")
        cls.validate_field(explanation, "explanation")

        if extra_context:
            cls.validate_field(extra_context, "extra_context")

    @classmethod
    def validate_primm_input(
        cls,
        code_snippet: str,
        user_prediction_text: str,
        user_explanation_text: str,
        prediction_prompt_text: str,
        actual_output_summary: Optional[str] = None,
    ) -> None:
        """
        Validate all fields in a PRIMM submission.

        :raises SuspiciousInputError: If input validation fails
        """
        cls.validate_field(code_snippet, "code")
        cls.validate_field(user_prediction_text, "prediction")
        cls.validate_field(user_explanation_text, "explanation")
        cls.validate_field(prediction_prompt_text, "topic")

        if actual_output_summary:
            cls.validate_field(actual_output_summary, "output_summary")

    @classmethod
    def validate_field(cls, text: str, field_name: str) -> None:
        """
        Validate a single input field using objective criteria.

        :raises SuspiciousInputError: If input validation fails
        """
        if not isinstance(text, str):
            raise SuspiciousInputError(f"{field_name} must be a string")

        # 1. Length check
        max_length = cls.MAX_LENGTHS.get(field_name, 2000)
        if len(text) > max_length:
            _LOGGER.warning(f"Length violation: {field_name} is {len(text)} chars (max {max_length})")
            raise SuspiciousInputError(f"{field_name} exceeds maximum length of {max_length} characters")

        # Empty strings are fine - Pydantic handles required fields
        if not text:
            return

        # 2. Control character check
        control_chars = sum(1 for c in text if ord(c) < 32 and c not in "\n\r\t")
        if control_chars > 0:
            control_percentage = (control_chars / len(text)) * 100
            if control_percentage > cls.MAX_CONTROL_CHAR_PERCENTAGE:
                _LOGGER.warning(f"Excessive control characters in {field_name}: {control_percentage:.1f}%")
                raise SuspiciousInputError(f"{field_name} contains too many control characters")

        # 3. Excessive markdown headers (structure injection)
        header_count = text.count("###")
        if header_count > cls.MAX_MARKDOWN_HEADERS:
            _LOGGER.warning(f"Excessive headers in {field_name}: {header_count} (max {cls.MAX_MARKDOWN_HEADERS})")
            raise SuspiciousInputError(f"{field_name} contains too many section headers")

        # 4. Code block markers in non-code fields (context escaping)
        if field_name != "code":
            code_block_count = text.count("```")
            if code_block_count > cls.MAX_CODE_BLOCKS:
                _LOGGER.warning(
                    f"Excessive code blocks in {field_name}: {code_block_count} (max {cls.MAX_CODE_BLOCKS})"
                )
                raise SuspiciousInputError(f"{field_name} contains too many code block markers")

        # 5. Consecutive special characters (obfuscation/injection attempts)
        max_consecutive = 0
        current_consecutive = 0
        for char in text:
            if not char.isalnum() and not char.isspace():
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        if max_consecutive > cls.MAX_CONSECUTIVE_SPECIAL_CHARS:
            _LOGGER.warning(f"Excessive consecutive special chars in {field_name}: {max_consecutive}")
            raise SuspiciousInputError(f"{field_name} contains unusual character sequences")

    @classmethod
    def sanitize_for_logging(cls, text: str, max_length: int = 100) -> str:
        """
        Sanitize text for safe logging (via truncation).

        :param text: Text to sanitize
        :param max_length: Maximum length to include in logs
        :returns: Sanitized text safe for logging
        """
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text
