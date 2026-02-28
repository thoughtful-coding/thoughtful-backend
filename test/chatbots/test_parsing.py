#!/usr/bin/env python3
import pytest

from thoughtful_backend.chatbots.parsing import JsonParseError, parse_json_response


def test_parse_json_response_clean_json():
    """Test parsing clean JSON."""
    result = parse_json_response('{"key": "value", "number": 42}')
    assert result == {"key": "value", "number": 42}


def test_parse_json_response_embedded_json():
    """Test parsing JSON embedded in other text."""
    result = parse_json_response('Here is the response: {"key": "value"} Hope that helps!')
    assert result == {"key": "value"}


def test_parse_json_response_markdown_wrapped():
    """Test parsing JSON wrapped in markdown code blocks."""
    text = '```json\n{"aiFeedback": "Good work!", "aiAssessment": "achieves"}\n```'
    result = parse_json_response(text)
    assert result == {"aiFeedback": "Good work!", "aiAssessment": "achieves"}


def test_parse_json_response_with_preamble():
    """Test parsing JSON with AI preamble text."""
    text = 'Based on my analysis, here is the evaluation:\n\n{"aiAssessment": "mostly"}'
    result = parse_json_response(text)
    assert result == {"aiAssessment": "mostly"}


def test_parse_json_response_nested_objects():
    """Test parsing JSON with nested objects."""
    text = '{"outer": {"inner": "value"}, "list": [1, 2, 3]}'
    result = parse_json_response(text)
    assert result == {"outer": {"inner": "value"}, "list": [1, 2, 3]}


def test_parse_json_response_invalid_json_raises_error():
    """Test that invalid JSON raises JsonParseError."""
    with pytest.raises(JsonParseError) as exc_info:
        parse_json_response("This is not JSON at all")
    assert "non-JSON response" in str(exc_info.value)
    assert exc_info.value.raw_text == "This is not JSON at all"


def test_parse_json_response_malformed_json_raises_error():
    """Test that malformed JSON raises JsonParseError."""
    with pytest.raises(JsonParseError):
        parse_json_response('{"key": "value"')  # Missing closing brace


def test_parse_json_response_empty_string_raises_error():
    """Test that empty string raises JsonParseError."""
    with pytest.raises(JsonParseError):
        parse_json_response("")
