import json
import logging
import typing

import pydantic
import requests

from thoughtful_backend.models.learning_entry_models import ChatBotFeedback
from thoughtful_backend.models.primm_feedback_models import PrimmEvaluationResponseModel

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)

CHATBOT_MODEL = "gemini-2.0-flash"


class ChatBotApiError(Exception):
    def __init__(self, msg: str, status_code: int = 503) -> None:
        super().__init__(msg)
        self.status_code = status_code


_PREDFINED_CODE_REFLECTION_FEEDBACK_PROMPT_TEMPLATE = """
You are an expert in programming and tutoring. Your task is to evaluate a student's
explanation of a given piece of Python code that illustrates how a particular topic
works. Provide short, concise, and constructive feedback and an assessment level on
their analysis of the given piece of code. Be mindful that these students are
learning and don't provide feedback that is beyond the level of the given example.

### Student's Submission Details

**Topic of Student's Analysis:** {topic}

**Code Student Was Given to Analyze:**

```python
{code}
```

**Student's Explanation:**

{explanation}

### Rubric for Assessment Levels

| Objective | Requirements/Specifications | Achieves | Mostly | Developing | Insufficient |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Well-written: Entry is well-written and displays level of care expected in other, writing-centered classes | Entry is brief and to the point: it is no longer than it has to be. Entry uses proper terminology. Entry has no obvious spelling mistakes Entry uses proper grammar  | Entry is of high quality without any obvious errors or extraneous information | Entry contains one or two errors and could only be shortened a little | Entry contains many errors and has a lot of unnecessary, repetitive information. |  |
| Thoughtful: Entry includes analysis that is easy to understand and could prove useful in the future | Analysis is about a topic that could conceivably come up in a future CS class. Analysis identifies single possible point of confusion. Analysis eliminates all possible confusion on the topic. Analysis references example. The phrase “as seen in the example” present in entry. | All requirements met. | Entry contains all but one of the requirements. | Entry's analysis is superficial an unfocused. |  |

### Instructions

Please provide your evaluation in a strict JSON format with the following structure and keys (use camelCase for keys).
For example:

```
{{
    "aiFeedback": "Your code is clear and accurately demonstrates the concept. Consider adding comments for better readability",
    "aiAssessment": "mostly",
}}
```

Valid `aiAssessment` values are: "achieves", "mostly", "developing", "insufficient".

IMPORTANT: Respond ONLY with the valid JSON object as described. Do not include
any other text, greetings, or conversational filler before or after the JSON.
"""


_REFLECTION_FEEDBACK_PROMPT_TEMPLATE = """
You are an expert in programming and tutoring. Your task is to evaluate a student's self-created
Python code example and their explanation for a chosen topic.

Provide short, concise, and constructive feedback. Your feedback should assess both the correctness
of the code and the clarity of the explanation. Be mindful that these are students, so your feedback
should not go too far beyond the scope of the topic they are trying to explain.

### Student's Submission Details

**Topic:** {topic}

**Student's Code:**

```python
{code}
```

**Student's Explanation:**

{explanation}

### Rubric for Assessment Levels

| Objective | Requirements/Specifications | Achieves | Mostly | Developing | Insufficient |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Well-written: Entry is well-written and displays level of care expected in other, writing-centered classes | Entry is brief and to the point: it is no longer than it has to be. Entry uses proper terminology. Entry has no obvious spelling mistakes Entry uses proper grammar  | Entry is of high quality without any obvious errors or extraneous information | Entry contains one or two errors and could only be shortened a little | Entry contains many errors and has a lot of unnecessary, repetitive information. |  |
| Thoughtful: Entry includes analysis that is easy to understand and could prove useful in the future | Analysis is about a topic that could conceivably come up in a future CS class. Analysis identifies single possible point of confusion. Analysis eliminates all possible confusion on the topic. Analysis references example. The phrase “as seen in the example” present in entry. | All requirements met. | Entry contains all but one of the requirements. | Entry's analysis is superficial an unfocused. |  |
| Grounded: Entry includes a pertinent example that gets to the heart of the topic being discussed. | Example highlights issue being discussed. Example doesn't include unnecessary, extraneous details or complexity. Example is properly formatted. Example doesn't include any obvious programming errors. | All requirements met | Entry contains all but one or two of the requirements. | Entry's example is difficult to understand or doesn't relate to the topic being discussed. |  |

### Instructions

Please provide your evaluation in a strict JSON format with the following structure and keys (use camelCase for keys).
For example:

```
{{
    "aiFeedback": "Your code is clear and accurately demonstrates the concept. Consider adding comments for better readability",
    "aiAssessment": "mostly",
}}
```

Valid `aiAssessment` values are: "achieves", "mostly", "developing", "insufficient".

IMPORTANT: Respond ONLY with the valid JSON object as described. Do not include
any other text, greetings, or conversational filler before or after the JSON.
"""

_PRIMM_EVALUATION_PROMPT_TEMPLATE = """
You are an expert Python programming assistant and an encouraging educational coach.
Your task is to evaluate a student's analysis of a given Python code snippet. The student has provided:

- Their initial prediction (in English) about what the code will do, made before running the code.
- Their confidence in that prediction.
- An explanation/self-correction, written after observing the code's output.

### Student's Submission Details:

**Python Code Snippet Analyzed**

```python
{code_snippet}
```

**Prompt Given to Student for Prediction:**

{prediction_prompt_text}

**Student's Initial Prediction:**

{user_prediction_text}

**Actual Code Output Summary (if any) as Observed by Student:**

{actual_output_summary}

**Student's Explanation/Self-Correction (after seeing output of program)**

{user_explanation_text}

### Evaluation Criteria & Instructions:

- aiPredictionAssessment:
    Based on the code_snippet and prediction_prompt_text, evaluate the specificity, accuracy,
    and relevance of the user_prediction_text.

    AssessmentLevel Rubric for Prediction:
        "achieves": Prediction is highly specific, accurate, directly addresses the prompt, and demonstrates clear foresight or understanding of code execution.
        "mostly": Prediction is largely correct and relevant but may miss some key details, nuances, or edge cases.
        "developing": Prediction shows some correct ideas but is vague, contains notable inaccuracies, or doesn't fully address the prompt.
        "insufficient": Prediction is significantly incorrect, off-topic, or too minimal (e.g., "it will run") to demonstrate understanding.

- aiExplanationAssessment:
    This part is only applicable if user_explanation_text is provided and meaningful. If
    user_explanation_text is empty, very short, or clearly not an attempt at explanation/
    correction, set explanationAssessment to null and omit explanationFeedback. Evaluate the
    quality of reasoning in user_explanation_text. Does it correctly identify why the code
    behaved as it did? If their prediction was inaccurate (compare user_prediction_text with
    actual_output_summary if available, or infer from their explanation), does their explanation
    show learning from the discrepancy?

    AssessmentLevel Rubric for Explanation/Self-Correction:
        "achieves": Explanation is clear, accurate, insightful. If correcting a mistake, it pinpoints the error in understanding and explains the correct mechanism well. If elaborating on a correct prediction, it demonstrates deep conceptual understanding.
        "mostly": Explanation is generally correct but might lack some depth, precision, or clarity. Minor inaccuracies might be present.
        "developing": Shows some effort to explain but contains significant misunderstandings, is unclear, or doesn't fully address the core reasons for the code's behavior or their prediction error.
        "insufficient": Explanation is largely incorrect, irrelevant, or too minimal to assess.

- aiOverallComment:
    Provide a brief, consolidated, encouraging overall comment. You can summarize key strengths or suggest general areas for continued focus.

### Instructions

Please provide your evaluation in a strict JSON format with the following structure and keys (use camelCase for keys):
```
{{
    "aiPredictionAssessment": "AssessmentLevel: string",
    "aiExplanationAssessment": "AssessmentLevel: string",
    "aiOverallComment": "Overall consolidated comment: string>"
}}
```

Valid `AssessmentLevel` values are: "achieves", "mostly", "developing", "insufficient".

IMPORTANT: Respond ONLY with the valid JSON object as described. Do not include any other text,
greetings, or conversational filler before or after the JSON.
"""


class ChatBotWrapper:
    def __init__(self) -> None:
        pass

    def _call_google_generative_api(
        self,
        *,
        chatbot_api_key: str,
        prompt: str,
        timeout_seconds: int = 45,
    ) -> dict:
        """
        Helper method to make the POST request to Google's Generative AI content generation.
        Handles common request setup and error handling.
        """
        api_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{CHATBOT_MODEL}:generateContent?key={chatbot_api_key}"
        request_payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 200},
        }

        try:
            response = requests.post(api_endpoint, json=request_payload, timeout=timeout_seconds)
            response.raise_for_status()
            api_response_data = response.json()

            candidates = api_response_data.get("candidates")
            if not isinstance(candidates, list) or len(candidates) == 0 or not candidates[0].get("content"):
                _LOGGER.error("Invalid or missing candidates/content in GenAI API response: %s", api_response_data)
                raise ChatBotApiError("AI service returned an unexpected response structure (no candidates/content).")

            parts = candidates[0]["content"].get("parts")
            if not isinstance(parts, list) or len(parts) == 0 or not parts[0].get("text"):
                _LOGGER.error("Invalid or missing parts/text in GenAI API response: %s", api_response_data)
                raise ChatBotApiError("AI service returned an unexpected response structure (no parts/text).")

            generated_text = str(parts[0]["text"])
            _LOGGER.info(f"Raw GenAI response text (first 500 chars): {generated_text[:500]}")

            try:
                json_start = generated_text.find("{")
                json_end = generated_text.rfind("}")
                if json_start != -1 and json_end != -1 and json_end > json_start:
                    json_str = generated_text[json_start : json_end + 1]
                    return json.loads(json_str)
                else:
                    return json.loads(generated_text)
            except json.JSONDecodeError as json_e:
                _LOGGER.error(f"Failed to parse. Error: {json_e}. Text: {generated_text}", exc_info=True)
                raise ChatBotApiError(f"AI returned non-JSON response. Content: {generated_text[:500]}")

        except requests.exceptions.Timeout:
            _LOGGER.error("Google GenAI API request timed out.")
            raise ChatBotApiError("AI service request timed out.", 504)
        except requests.exceptions.RequestException as e:
            _LOGGER.error(f"Google GenAI API request failed: {e}")
            if e.response is not None:
                _LOGGER.error(f"GenAI API Error Response: {e.response.text}")
            raise ChatBotApiError(f"Failed to communicate with AI service: {str(e)}")
        except ValueError as e:
            _LOGGER.error(f"ValueError during AI call or response processing: {e}", exc_info=True)
            raise ChatBotApiError(f"ValueError during AI call or response processing: {str(e)}")
        except (KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
            _LOGGER.error(f"Error processing AI response: {e}. Raw Response: {response}")
            raise ChatBotApiError(f"Invalid or unexpected response from AI service: {str(e)}")

    def generate_reflection_feedback_prompt(
        self,
        *,
        topic: str,
        is_topic_predefined: bool,
        code: str,
        is_code_predefined: bool,
        explanation: str,
    ) -> str:
        if is_code_predefined:
            return _PREDFINED_CODE_REFLECTION_FEEDBACK_PROMPT_TEMPLATE.format(
                topic=topic, code=code, explanation=explanation
            )
        else:
            return _REFLECTION_FEEDBACK_PROMPT_TEMPLATE.format(topic=topic, code=code, explanation=explanation)

    def call_reflection_api(
        self,
        *,
        chatbot_api_key: str,
        topic: str,
        is_topic_predefined: bool,
        code: str,
        is_code_predefined: bool,
        explanation: str,
    ) -> ChatBotFeedback:
        prompt = self.generate_reflection_feedback_prompt(
            topic=topic,
            is_topic_predefined=is_topic_predefined,
            code=code,
            is_code_predefined=is_code_predefined,
            explanation=explanation,
        )
        generated_dict = self._call_google_generative_api(
            chatbot_api_key=chatbot_api_key,
            prompt=prompt,
            timeout_seconds=45,
        )

        try:
            return ChatBotFeedback(**generated_dict)
        except ValueError as e:
            _LOGGER.error(f"Error parsing API response: {e}. Raw data: {generated_dict}", exc_info=True)
            raise ValueError(f"Invalid or unexpected response structure from AI for PRIMM: {str(e)}")

    def generate_primm_feedback_prompt(
        self,
        *,
        code_snippet: str,
        prediction_prompt_text: str,
        user_prediction_text: str,
        user_explanation_text: str,
        actual_output_summary: typing.Optional[str],
    ) -> str:
        return _PRIMM_EVALUATION_PROMPT_TEMPLATE.format(
            code_snippet=code_snippet,
            prediction_prompt_text=prediction_prompt_text,
            user_prediction_text=user_prediction_text,
            user_explanation_text=user_explanation_text,
            actual_output_summary=actual_output_summary or "Not provided.",
        )

    def call_primm_evaluation_api(
        self,
        *,
        chatbot_api_key: str,
        code_snippet: str,
        prediction_prompt_text: str,
        user_prediction_text: str,
        user_explanation_text: str,
        actual_output_summary: typing.Optional[str],
    ) -> PrimmEvaluationResponseModel:
        prompt = self.generate_primm_feedback_prompt(
            code_snippet=code_snippet,
            prediction_prompt_text=prediction_prompt_text,
            user_prediction_text=user_prediction_text,
            user_explanation_text=user_explanation_text,
            actual_output_summary=actual_output_summary,
        )
        generated_dict = self._call_google_generative_api(
            chatbot_api_key=chatbot_api_key,
            prompt=prompt,
            timeout_seconds=60,
        )

        try:
            response = PrimmEvaluationResponseModel.model_validate(generated_dict)
            _LOGGER.info(f"Parsed: {response.model_dump_json(indent=2, exclude_none=True)}")
            return response

        except (pydantic.ValidationError, ValueError) as e:
            _LOGGER.error(f"Error parsing API response: {e}. Raw data: {generated_dict}", exc_info=True)
            raise ValueError(f"Invalid or unexpected response structure from AI for PRIMM: {str(e)}")
