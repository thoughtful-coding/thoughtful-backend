import json
import logging
import typing

import requests

from aws_src_sample.models.learning_entry_models import AssessmentLevel, ChatBotFeedback

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


_PROMPT = """
You are an automated Python code assessor. Your task is to evaluate a student's
Python code example and explanation based on a specified topic. Provide
constructive feedback and an assessment level.

**Topic:** {topic}

**Student's Code:**
```python
{code}
```

**Student's Explanation:**
{explanation}

**Rubric for Assessment Levels:**
| Objective | Requirements/Specifications | Achieves | Mostly | Developing | Insufficient |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Well-written: Entry is well-written and displays level of care expected in other, writing-centered classes | Entry is brief and to the point: it is no longer than it has to be. Entry uses proper terminology. Entry has no obvious spelling mistakes Entry uses proper grammar  | Entry is of high quality without any obvious errors or extraneous information | Entry contains one or two errors and could only be shortened a little | Entry contains many errors and has a lot of unnecessary, repetitive information. |  |
| Thoughtful: Entry includes analysis that is easy to understand and could prove useful in the future | Analysis is about a topic that could conceivably come up in a future CS class. Analysis identifies single possible point of confusion. Analysis eliminates all possible confusion on the topic. Analysis references example. The phrase “as seen in the example” present in entry. | All requirements met. | Entry contains all but one of the requirements. | Entry's analysis is superficial an unfocused. |  |
| Grounded: Entry includes a pertinent example that gets to the heart of the topic being discussed. | Example highlights issue being discussed. Example doesn't include unnecessary, extraneous details or complexity. Example is properly formatted. Example doesn't include any obvious programming errors. | All requirements met | Entry contains all but one or two of the requirements. | Entry's example is difficult to understand or doesn't relate to the topic being discussed. |  |

**Provide your response in a concise format. Start with the assessment level, then provide the feedback. For example:
Assessment: Mostly
Feedback: Your code is clear and accurately demonstrates the concept. Consider adding comments for better readability.**`;
"""

CHATBOT_MODEL = "gemini-2.0-flash"


def generate_chatbot_feedback_prompt(*, topic: str, code: str, explanation: str) -> str:
    return _PROMPT.format(topic, code, explanation)


def call_google_genai_api(
    *,
    chatbot_api_key: str,
    topic: str,
    code: str,
    explanation: str,
) -> ChatBotFeedback:
    """
    Calls the Google Generative AI API.
    submission_content expects: userTopic, userCode, userExplanation from ReflectionInteractionInput.
    """
    api_endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{CHATBOT_MODEL}:generateContent?key={chatbot_api_key}"
    )
    request_payload = {
        "contents": [
            {"parts": [{"text": generate_chatbot_feedback_prompt(topic=topic, code=code, explanation=explanation)}]}
        ]
    }

    try:
        _LOGGER.info(f"Calling GenAI API for topic: {topic}")
        response = requests.post(api_endpoint, json=request_payload, timeout=45)
        response.raise_for_status()
        data = response.json()

        candidates = data.get("candidates")
        if (
            not candidates
            or not isinstance(candidates, list)
            or len(candidates) == 0
            or not candidates[0].get("content")
        ):
            _LOGGER.error("Invalid or missing candidates/content in GenAI API response: %s", data)
            raise ValueError("AI service returned an unexpected response structure (no candidates/content).")

        parts = candidates[0]["content"].get("parts")
        if not parts or not isinstance(parts, list) or len(parts) == 0 or not parts[0].get("text"):
            _LOGGER.error("Invalid or missing parts/text in GenAI API response: %s", data)
            raise ValueError("AI service returned an unexpected response structure (no parts/text).")

        generated_text = parts[0]["text"]
        _LOGGER.info(f"Raw GenAI response text (first 500 chars): {generated_text[:500]}")

        ai_feedback = "Could not parse AI feedback."
        ai_assessment_str: AssessmentLevel = "insufficient"  # Default

        assessment_keywords = ["achieves", "mostly", "developing", "insufficient"]
        parsed_assessment_keyword = None

        # More robust parsing for "Assessment: <level>"
        assessment_line_found = ""
        for line in generated_text.lower().splitlines():
            if line.startswith("assessment:"):
                assessment_line_found = line
                break

        if assessment_line_found:
            found_level = assessment_line_found.replace("assessment:", "").strip()
            if found_level in assessment_keywords:
                parsed_assessment_keyword = found_level

        if not parsed_assessment_keyword:  # Fallback if "Assessment:" line not clear
            for keyword in assessment_keywords:
                if keyword in generated_text.lower():
                    parsed_assessment_keyword = keyword
                    break

        assert parsed_assessment_keyword in ("mostly", "achieves", "insufficient", "developing")
        ai_assessment_str: AssessmentLevel = parsed_assessment_keyword or "insufficient"

        # Feedback parsing
        feedback_index = generated_text.lower().find("feedback:")
        if feedback_index != -1:
            ai_feedback = generated_text[feedback_index + len("feedback:") :].strip()
        elif parsed_assessment_keyword:
            # Attempt to remove the assessment line more cleanly if it was found
            # This part can be tricky if the format isn't perfectly consistent
            lines = generated_text.splitlines()
            temp_feedback_lines = []
            assessment_line_prefix_to_remove = f"assessment: {ai_assessment_str}"
            for line in lines:
                if not line.lower().strip().startswith(assessment_line_prefix_to_remove):
                    temp_feedback_lines.append(line)
            ai_feedback = "\n".join(temp_feedback_lines).strip()
            if not ai_feedback:  # If removing leaves it empty, default to original text
                ai_feedback = generated_text.strip()
        else:
            ai_feedback = generated_text.strip()

        _LOGGER.info(f"Parsed AI Assessment: {ai_assessment_str}, Feedback Preview: {ai_feedback[:100]}")
        return ChatBotFeedback(ai_feedback, ai_assessment_str)

    except requests.exceptions.Timeout:
        _LOGGER.error("Google GenAI API request timed out.")
        raise TimeoutError("AI service request timed out.")
    except requests.exceptions.RequestException as e:
        _LOGGER.error(f"Google GenAI API request failed: {e}")
        if e.response is not None:
            _LOGGER.error(f"GenAI API Error Response: {e.response.text}")
        raise ConnectionError(f"Failed to communicate with AI service: {str(e)}")
    except (KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
        _LOGGER.error(
            f"Error processing Google GenAI API response: {e}. Raw Response: {data if 'data' in locals() else 'N/A'}"
        )
        raise ValueError(f"Invalid or unexpected response from AI service: {str(e)}")
