"""
Claude (Anthropic) provider implementation.
"""

import logging

import anthropic

from thoughtful_backend.chatbots.parsing import JsonParseError, parse_json_response

_LOGGER = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-haiku-4-5-20251001"


class ClaudeApiError(Exception):
    def __init__(self, msg: str, status_code: int = 503) -> None:
        super().__init__(msg)
        self.status_code = status_code


def call_claude_api(
    *,
    api_key: str,
    prompt: str,
    timeout_seconds: int = 45,
) -> dict:
    """
    Call Claude API for content generation.

    :param api_key: Anthropic API key
    :param prompt: The formatted prompt to send to the AI
    :param timeout_seconds: Request timeout in seconds
    :return: Parsed JSON response from the AI
    :raises ClaudeApiError: If the API call fails or returns invalid data
    """
    try:
        client = anthropic.Anthropic(api_key=api_key, timeout=timeout_seconds)

        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            temperature=0.3,
            system="Be concise. Limit each feedback field to 2-3 sentences and under 500 characters.",
            messages=[{"role": "user", "content": prompt}],
        )

        if not message.content or len(message.content) == 0:
            _LOGGER.error("Empty response from Claude API")
            raise ClaudeApiError("AI service returned an empty response.")

        first_block = message.content[0]
        if first_block.type != "text":
            _LOGGER.error(f"Unexpected content type from Claude: {first_block.type}")
            raise ClaudeApiError("AI service returned unexpected content type.")

        generated_text = first_block.text
        _LOGGER.info(f"Raw Claude response text (first 500 chars): {generated_text[:500]}")

        try:
            return parse_json_response(generated_text)
        except JsonParseError as e:
            raise ClaudeApiError(str(e))

    except anthropic.APITimeoutError:
        _LOGGER.error("Claude API request timed out.")
        raise ClaudeApiError("AI service request timed out.", 504)
    except anthropic.APIConnectionError as e:
        _LOGGER.error(f"Claude API connection error: {e}")
        raise ClaudeApiError(f"Failed to connect to AI service: {str(e)}")
    except anthropic.RateLimitError as e:
        _LOGGER.error(f"Claude API rate limit exceeded: {e}")
        raise ClaudeApiError("AI service rate limit exceeded.", 429)
    except anthropic.APIStatusError as e:
        _LOGGER.error(f"Claude API error: {e.status_code} - {e.message}")
        raise ClaudeApiError(f"AI service error: {e.message}", e.status_code)
    except anthropic.APIError as e:
        _LOGGER.error(f"Claude API error: {e}")
        raise ClaudeApiError(f"AI service error: {str(e)}")
    except ClaudeApiError:
        raise
    except Exception as e:
        _LOGGER.error(f"Error processing Claude API response: {e}", exc_info=True)
        raise ClaudeApiError(f"Invalid or unexpected response from AI service: {str(e)}")
