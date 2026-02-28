"""
Gemini (Google Generative AI) provider implementation.
"""

import logging

import requests

from thoughtful_backend.chatbots.parsing import JsonParseError, parse_json_response

_LOGGER = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"


class GeminiApiError(Exception):
    def __init__(self, msg: str, status_code: int = 503) -> None:
        super().__init__(msg)
        self.status_code = status_code


def call_gemini_api(
    *,
    api_key: str,
    prompt: str,
    timeout_seconds: int = 45,
) -> dict:
    """
    Make a POST request to Google's Generative AI content generation API.

    :param api_key: Google Generative AI API key
    :param prompt: The formatted prompt to send to the AI
    :param timeout_seconds: Request timeout in seconds
    :return: Parsed JSON response from the AI
    :raises GeminiApiError: If the API call fails or returns invalid data
    """
    api_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    request_payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 1024,
            "temperature": 0.3,
            "thinkingConfig": {"thinkingBudget": 0},
        },
        "safetySettings": [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE",
            },
        ],
    }

    try:
        response = requests.post(api_endpoint, json=request_payload, headers=headers, timeout=timeout_seconds)
        response.raise_for_status()
        api_response_data = response.json()

        candidates = api_response_data.get("candidates")
        if not isinstance(candidates, list) or len(candidates) == 0 or not candidates[0].get("content"):
            _LOGGER.error("Invalid or missing candidates/content in GenAI API response: %s", api_response_data)
            raise GeminiApiError("AI service returned an unexpected response structure (no candidates/content).")

        parts = candidates[0]["content"].get("parts")
        if not isinstance(parts, list) or len(parts) == 0 or not parts[0].get("text"):
            _LOGGER.error("Invalid or missing parts/text in GenAI API response: %s", api_response_data)
            raise GeminiApiError("AI service returned an unexpected response structure (no parts/text).")

        generated_text = str(parts[0]["text"])
        _LOGGER.info(f"Raw Gemini response text (first 500 chars): {generated_text[:500]}")

        try:
            return parse_json_response(generated_text)
        except JsonParseError as e:
            raise GeminiApiError(str(e))

    except requests.exceptions.Timeout:
        _LOGGER.error("Gemini API request timed out.")
        raise GeminiApiError("AI service request timed out.", 504)
    except requests.exceptions.RequestException as e:
        _LOGGER.error(f"Gemini API request failed: {e}")
        if e.response is not None:
            _LOGGER.error(f"Gemini API Error Response: {e.response.text}")
        raise GeminiApiError(f"Failed to communicate with AI service: {str(e)}")
    except GeminiApiError:
        raise
    except Exception as e:
        _LOGGER.error(f"Error processing Gemini API response: {e}", exc_info=True)
        raise GeminiApiError(f"Invalid or unexpected response from AI service: {str(e)}")
