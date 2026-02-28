"""
Shared utilities for parsing AI provider responses.
"""

import json
import logging

_LOGGER = logging.getLogger(__name__)


class JsonParseError(Exception):
    """Raised when JSON parsing fails."""

    def __init__(self, msg: str, raw_text: str) -> None:
        super().__init__(msg)
        self.raw_text = raw_text


def parse_json_response(generated_text: str) -> dict:
    """
    Parse JSON from generated text, handling cases where JSON is embedded in other text.

    :param generated_text: Raw text from the AI provider
    :return: Parsed JSON as a dictionary
    :raises JsonParseError: If JSON parsing fails
    """
    try:
        json_start = generated_text.find("{")
        json_end = generated_text.rfind("}")
        if json_start != -1 and json_end != -1 and json_end > json_start:
            json_str = generated_text[json_start : json_end + 1]
            return json.loads(json_str)
        else:
            return json.loads(generated_text)
    except json.JSONDecodeError as e:
        _LOGGER.error(f"Failed to parse JSON. Error: {e}. Text: {generated_text}", exc_info=True)
        raise JsonParseError(f"AI returned non-JSON response. Content: {generated_text[:500]}", generated_text)
