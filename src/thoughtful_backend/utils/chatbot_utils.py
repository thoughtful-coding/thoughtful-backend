import json
import logging
import typing

import pydantic
import requests

from thoughtful_backend.models.learning_entry_models import ChatBotFeedback
from thoughtful_backend.models.primm_feedback_models import PrimmEvaluationResponseModel
from thoughtful_backend.utils.input_validator import InputValidator

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)

CHATBOT_MODEL = "gemini-2.5-flash"


class ChatBotApiError(Exception):
    def __init__(self, msg: str, status_code: int = 503) -> None:
        super().__init__(msg)
        self.status_code = status_code


_PREDFINED_CODE_REFLECTION_FEEDBACK_PROMPT_TEMPLATE = """
You are an expert in programming and tutoring. Your task is to evaluate a student's
explanation of a piece of code they were given. Their explanation should explain
how the code works and how it pertains to the specific topic they were also given.

Provide short, concise, and constructive feedback and an assessment level on their
analysis of the given piece of code. Be mindful that these are students, so your
feedback should not go beyond the scope of the topic they are trying to explain.
Put another way, these students are learning, so ONLY give them feedback on what
they said. Do not make suggestions that are beyond the exact topic they are
discussing.

### Student's Submission Details

**Context of Where the Student Is/What They Know:**

```
{extra_context_section}
```

**Topic Student was Given to Reflect Upon:** {topic}

**Code Student Was Given to Analyze:**

```python
{code}
```

**Student's Explanation:**

```
{explanation}
```

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
"journal entry". The entry is on a topic of their choosing and contains a short Python code example
and a short explanation of how the code works and how it pertains to their chosen topic.

Provide short, concise, and constructive feedback. Your feedback should assess both the correctness
of the code and the clarity of the explanation. Be mindful that these are students, so
your feedback should not go beyond the scope of the topic they are trying to explain.
Put another way, these students are learning, so ONLY give them feedback on what
they said. Do not make suggestions that are beyond the exact topic they are discussing.

### Student's Submission Details

**Context of Where the Student Is/What They Know:**

```
{extra_context_section}
```

**Student's Chosen Topic:** {topic}

**Student's Code:**

```python
{code}
```

**Student's Explanation:**

{explanation}

{extra_context_section}

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
    "aiOverallComment": "Overall consolidated comment: string"
}}
```

Valid `AssessmentLevel` values are: "achieves", "mostly", "developing", "insufficient".

IMPORTANT: Respond ONLY with the valid JSON object as described. Do not include any other text,
greetings, or conversational filler before or after the JSON.
"""


class ChatBotWrapper:
    # Maximum allowed length for AI-generated feedback
    MAX_FEEDBACK_LENGTH = 500

    def __init__(self) -> None:
        pass

    @classmethod
    def _validate_output_length(cls, text: str, field_name: str) -> None:
        """
        Validates that AI-generated output doesn't exceed safe limits.
        Prevents AI from being manipulated into generating excessive content.

        :param text: The AI-generated text to validate
        :param field_name: Name of the field for error messages
        :raises ChatBotApiError: If output exceeds maximum length
        """
        if len(text) > cls.MAX_FEEDBACK_LENGTH:
            _LOGGER.error(f"AI output too long: {field_name} is {len(text)} chars (max {cls.MAX_FEEDBACK_LENGTH})")
            raise ChatBotApiError(
                f"AI response validation failed: {field_name} exceeds maximum length", status_code=500
            )

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

        :param chatbot_api_key: Google Generative AI API key
        :param prompt: The formatted prompt to send to the AI
        :param timeout_seconds: Request timeout in seconds
        :return: Parsed JSON response from the AI
        :raises ChatBotApiError: If the API call fails or returns invalid data
        """
        api_endpoint = (
            f"https://generativelanguage.googleapis.com/v1/models/{CHATBOT_MODEL}:generateContent?key={chatbot_api_key}"
        )
        request_payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 200,  # Limit output size
                "temperature": 0.3,  # Lower = more consistent, less creative
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
        extra_context: typing.Optional[str] = None,
    ) -> str:
        """
        Generates the formatted prompt for reflection feedback evaluation.
        Selects appropriate template based on whether code is predefined or student-created.

        :param topic: The topic being analyzed
        :param is_topic_predefined: Whether the topic was provided or student-chosen
        :param code: The Python code being analyzed
        :param is_code_predefined: Whether code was provided or student-written
        :param explanation: Student's explanation of the code
        :param extra_context: Optional instructor-provided evaluation context
        :return: Formatted prompt string for AI evaluation
        """
        # Format the extra context section if provided
        extra_context_section = ""
        if extra_context:
            extra_context_section = f"### Additional Context for Evaluation\n\n{extra_context}"

        if is_code_predefined:
            return _PREDFINED_CODE_REFLECTION_FEEDBACK_PROMPT_TEMPLATE.format(
                topic=topic, code=code, explanation=explanation, extra_context_section=extra_context_section
            )
        else:
            return _REFLECTION_FEEDBACK_PROMPT_TEMPLATE.format(
                topic=topic, code=code, explanation=explanation, extra_context_section=extra_context_section
            )

    def call_reflection_api(
        self,
        *,
        chatbot_api_key: str,
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

        :param chatbot_api_key: Google Generative AI API key
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
        # Validate inputs before calling AI API
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
        generated_dict = self._call_google_generative_api(
            chatbot_api_key=chatbot_api_key,
            prompt=prompt,
            timeout_seconds=45,
        )

        try:
            feedback = ChatBotFeedback(**generated_dict)

            # Validate output length (prevent AI manipulation)
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

        :param code_snippet: The Python code snippet to evaluate
        :param prediction_prompt_text: The prediction question/prompt
        :param user_prediction_text: Student's prediction of code output
        :param user_explanation_text: Student's explanation of how code works
        :param actual_output_summary: Summary of actual code execution output
        :return: Formatted prompt string for AI evaluation
        """
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
        """
        Calls the AI API to evaluate a student's PRIMM activity submission.
        Validates input before calling API and validates output length to prevent manipulation.

        :param chatbot_api_key: Google Generative AI API key
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
        # Validate inputs before calling AI API
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
        generated_dict = self._call_google_generative_api(
            chatbot_api_key=chatbot_api_key,
            prompt=prompt,
            timeout_seconds=60,
        )

        try:
            response = PrimmEvaluationResponseModel.model_validate(generated_dict)
            _LOGGER.info(f"Parsed: {response.model_dump_json(indent=2, exclude_none=True)}")

            # Validate output length (prevent AI manipulation)
            self._validate_output_length(response.aiOverallComment, "aiOverallComment")

            return response

        except (pydantic.ValidationError, ValueError) as e:
            _LOGGER.error(f"Error parsing API response: {e}. Raw data: {generated_dict}", exc_info=True)
            raise ValueError(f"Invalid or unexpected response structure from AI for PRIMM: {str(e)}")
