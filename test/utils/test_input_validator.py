#!/usr/bin/env python3
"""
Tests for input validation with objective, measurable criteria.
"""

import pytest

from thoughtful_backend.utils.input_validator import InputValidator, SuspiciousInputError


class TestInputValidatorLegitimateInput:
    """Test that legitimate student submissions pass validation"""

    def test_valid_reflection_submission(self):
        """Normal reflection submission should pass"""
        InputValidator.validate_reflection_input(
            topic="For Loops in Python",
            code="for i in range(10):\n    print(i)",
            explanation="This code demonstrates a for loop that iterates from 0 to 9 and prints each number.",
        )

    def test_valid_with_extra_context(self):
        """Submission with instructor context should pass"""
        InputValidator.validate_reflection_input(
            topic="List Comprehensions",
            code="squares = [x**2 for x in range(5)]",
            explanation="This creates a list of squared numbers using list comprehension syntax.",
            extra_context="Focus on code efficiency and readability.",
        )

    def test_code_with_legitimate_backticks(self):
        """Code field can contain backticks"""
        InputValidator.validate_field("def foo():\n    # Use `print()` to display output\n    print('Hello')", "code")

    def test_explanation_with_legitimate_markdown(self):
        """Explanation can have reasonable markdown formatting"""
        InputValidator.validate_field(
            "The code uses **list comprehension** which is more *efficient* than a regular for loop.", "explanation"
        )


class TestInputValidatorLengthLimits:
    """Test length validation"""

    def test_topic_too_long(self):
        """Topic exceeding 200 chars should be rejected"""
        with pytest.raises(SuspiciousInputError, match="exceeds maximum length"):
            InputValidator.validate_field("A" * 201, "topic")

    def test_code_too_long(self):
        """Code exceeding 5000 chars should be rejected"""
        with pytest.raises(SuspiciousInputError, match="exceeds maximum length"):
            InputValidator.validate_field("print('x')\n" * 1000, "code")

    def test_explanation_too_long(self):
        """Explanation exceeding 2000 chars should be rejected"""
        with pytest.raises(SuspiciousInputError, match="exceeds maximum length"):
            InputValidator.validate_field("This is a long explanation. " * 100, "explanation")

    def test_extra_context_too_long(self):
        """Extra context exceeding 1000 chars should be rejected"""
        with pytest.raises(SuspiciousInputError, match="exceeds maximum length"):
            InputValidator.validate_field("Focus on " * 200, "extra_context")

    def test_topic_at_max_length(self):
        """Topic at exactly 200 chars should pass"""
        InputValidator.validate_field("A" * 200, "topic")

    def test_code_at_reasonable_length(self):
        """Reasonable code length should pass"""
        code = "def function():\n    pass\n" * 50
        InputValidator.validate_field(code, "code")


class TestInputValidatorStructuralLimits:
    """Test structural limits (headers, code blocks)"""

    def test_excessive_headers_in_explanation(self):
        """Detect too many markdown headers"""
        with pytest.raises(SuspiciousInputError, match="too many section headers"):
            InputValidator.validate_field("### Section 1\n### Section 2\n### Section 3\n### Section 4", "explanation")

    def test_three_headers_allowed(self):
        """Up to 3 headers should be allowed"""
        InputValidator.validate_field("### Section 1\n### Section 2\n### Section 3", "explanation")

    def test_code_block_markers_in_explanation(self):
        """Excessive code blocks in explanation should be rejected"""
        with pytest.raises(SuspiciousInputError, match="too many code block markers"):
            InputValidator.validate_field(
                "This is ```example one``` and ```example two``` and ```example three```", "explanation"
            )

    def test_code_field_allows_backticks(self):
        """Code field should allow backticks"""
        legitimate_code = """
def example():
    # You can use `print()` or `return`
    print("Hello")
"""
        InputValidator.validate_field(legitimate_code, "code")


class TestInputValidatorControlCharacters:
    """Test control character detection"""

    def test_normal_whitespace_allowed(self):
        """Normal whitespace (newlines, tabs) should be allowed"""
        text = "Line 1\nLine 2\tTabbed\r\nLine 3"
        InputValidator.validate_field(text, "explanation")

    def test_excessive_control_chars_blocked(self):
        """Too many control characters should be blocked"""
        # Create text with 10% control chars (bell chars)
        text = "a" * 90 + "\x07" * 10
        with pytest.raises(SuspiciousInputError, match="too many control characters"):
            InputValidator.validate_field(text, "explanation")

    def test_unicode_characters_allowed(self):
        """Unicode should pass"""
        InputValidator.validate_field("This code uses π (pi): pi = 3.14159", "explanation")


class TestInputValidatorConsecutiveSpecialChars:
    """Test consecutive special character limits"""

    def test_excessive_consecutive_special_chars(self):
        """Too many consecutive special characters should be blocked"""
        with pytest.raises(SuspiciousInputError, match="unusual character sequences"):
            InputValidator.validate_field("This is @@@@@@@@@@@ suspicious", "explanation")

    def test_normal_punctuation_allowed(self):
        """Normal punctuation should pass"""
        InputValidator.validate_field(
            "This is a sentence! It has punctuation, like commas and periods. Great?", "explanation"
        )

    def test_code_operators_allowed(self):
        """Code operators should be fine"""
        InputValidator.validate_field("x = y + z * (a - b) / c ** 2", "code")

    def test_ten_consecutive_special_chars_allowed(self):
        """Exactly 10 consecutive special chars should be allowed"""
        InputValidator.validate_field("Test ==========", "explanation")

    def test_eleven_consecutive_special_chars_blocked(self):
        """11 consecutive special chars should be blocked"""
        with pytest.raises(SuspiciousInputError, match="unusual character sequences"):
            InputValidator.validate_field("Test ===========", "explanation")


class TestInputValidatorCompleteReflection:
    """Test validation of complete reflection submissions"""

    def test_all_fields_valid(self):
        """Complete valid submission should pass"""
        InputValidator.validate_reflection_input(
            topic="Python Functions",
            code="def greet(name):\n    return f'Hello, {name}!'",
            explanation="This function takes a name parameter and returns a greeting string using f-string formatting.",
            extra_context="Pay attention to the use of f-strings.",
        )

    def test_validation_fails_on_bad_field(self):
        """Validation should fail if any field is invalid"""
        with pytest.raises(SuspiciousInputError):
            InputValidator.validate_reflection_input(
                topic="Loops",
                code="for i in range(10): print(i)",
                explanation="A" * 3000,  # Too long
                extra_context="Focus on syntax",
            )

    def test_validation_with_none_extra_context(self):
        """Validation should work when extra_context is None"""
        InputValidator.validate_reflection_input(
            topic="Variables",
            code="x = 5",
            explanation="This assigns the value 5 to variable x.",
            extra_context=None,
        )


class TestInputValidatorEdgeCases:
    """Test edge cases"""

    def test_empty_string_fields(self):
        """Empty strings should pass (Pydantic handles required)"""
        InputValidator.validate_field("", "topic")
        InputValidator.validate_field("", "code")
        InputValidator.validate_field("", "explanation")

    def test_multiline_content(self):
        """Multiline content should be validated properly"""
        multiline = """
        This is a detailed explanation.
        It spans multiple lines.
        Each line describes a different aspect.
        """
        InputValidator.validate_field(multiline, "explanation")


class TestInputValidatorSanitization:
    """Test log sanitization utility"""

    def test_sanitize_long_text(self):
        """Long text should be truncated for logging"""
        long_text = "A" * 200
        sanitized = InputValidator.sanitize_for_logging(long_text, max_length=50)
        assert len(sanitized) == 53  # 50 + "..."
        assert sanitized.endswith("...")

    def test_sanitize_short_text(self):
        """Short text should not be truncated"""
        short_text = "Hello world"
        sanitized = InputValidator.sanitize_for_logging(short_text, max_length=50)
        assert sanitized == short_text
        assert not sanitized.endswith("...")
