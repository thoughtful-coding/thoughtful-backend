"""
Prompt templates for AI-powered feedback on student submissions.
"""

PREDEFINED_CODE_REFLECTION_PROMPT = """
You are an expert in programming and tutoring. Your task is to evaluate a student's
reflection on a piece of code they were given. The student should explain how the
code works and how it relates to the specific topic they were given.

Be concise and constructive. Only give feedback on what the student said — do not
suggest improvements beyond the **exact topic they are discussing**. These are
learners; stay within scope and match your answers to the difficulty of the code.
Beginner code should result in beginner friendly explanations.

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

### Assessment Rubric

Evaluate on two dimensions: how well-written the entry is, and how thoughtful the analysis is.
Use the weakest dimension to determine the overall assessment level.

- Well-written: The entry is brief and to the point, uses proper terminology, has no obvious
  spelling or grammar mistakes, and contains no unnecessary or repetitive information.

- Thoughtful: The entry analyzes the given topic with depth and care. The entry either explains
  how the given topic works OR identifies a specific point of confusion around the topic and
  explains how to eliminates that confusion clearly. The entry references the example (e.g.
  uses a phrase like "as seen in the example"). The analysis is focused and could prove useful
  to the student in the future.

AssessmentLevel Rubric:
    "achieves": Both dimensions are fully met — entry is well-written and the analysis is
        specific, clear, and references the example.
    "mostly": One minor gap — e.g. analysis is good but has a small writing error, or is
        well-written but missing one requirement such as referencing the example.
    "developing": Notable gaps in one or both dimensions — e.g. analysis is superficial or
        unfocused, or writing has many errors and unnecessary content.
    "insufficient": Does not demonstrate a genuine attempt to explain the code or address
        the topic.

### Instructions

Be concise. Keep aiFeedback to 2-3 sentences maximum.

Please provide your evaluation in a strict JSON format with the following structure and keys (use camelCase for keys):

```
{{
    "aiFeedback": "<2-3 sentence constructive feedback>",
    "aiAssessment": "<achieves|mostly|developing|insufficient>"
}}
```

Valid `aiAssessment` values are: "achieves", "mostly", "developing", "insufficient".

IMPORTANT: Respond ONLY with the valid JSON object as described. Do not include
any other text, greetings, or conversational filler before or after the JSON.
"""


STUDENT_CODE_REFLECTION_PROMPT = """
You are an expert in programming and tutoring. Your task is to evaluate a student's reflection
on a piece of code they wrote. The entry is on a topic of their choosing and contains a short
Python code example and a short explanation of how the code works and how it pertains to their
chosen topic.

Be concise and constructive. Assess both the correctness of the code and the clarity of the
explanation. Only give feedback on what the student said — do not suggest improvements beyond
the **exact topic they are discussing**. These are learners; stay within scope and match your
answers to the difficulty of the code. Beginner code should result in beginner friendly
explanations.

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

```
{explanation}
```

### Assessment Rubric

Evaluate on three dimensions: how well-grounded the code example is, how well-written the
entry is, and how thoughtful the analysis is. Use the weakest dimension to determine the overall
assessment level.

- Grounded: The code example highlights the topic being discussed, doesn't include unnecessary
  complexity, is properly formatted, and contains no obvious programming errors.

- Well-written: The entry is brief and to the point, uses proper terminology, has no obvious
  spelling or grammar mistakes, and contains no unnecessary or repetitive information.

- Thoughtful: The entry analyzes the given topic with depth and care. The entry either explains
  how the given topic works OR identifies a specific point of confusion around the topic and
  explains how to eliminates that confusion clearly. The entry references the example (e.g.
  uses a phrase like "as seen in the example"). The analysis is focused and could prove useful
  to the student in the future.

AssessmentLevel Rubric:
    "achieves": All three dimensions are fully met.
    "mostly": One minor gap across the dimensions — e.g. one small writing error, analysis
        missing a single requirement, or example has a minor formatting issue.
    "developing": Notable gaps in one or more dimensions — e.g. analysis is superficial,
        code example is confusing or off-topic, or writing has many errors.
    "insufficient": Does not demonstrate a genuine attempt at a well-written, thoughtful,
        or grounded entry.

### Instructions

Be concise. Keep aiFeedback to 2-3 sentences maximum.

Please provide your evaluation in a strict JSON format with the following structure and keys (use camelCase for keys):

```
{{
    "aiFeedback": "<2-3 sentence constructive feedback>",
    "aiAssessment": "<achieves|mostly|developing|insufficient>"
}}
```

Valid `aiAssessment` values are: "achieves", "mostly", "developing", "insufficient".

IMPORTANT: Respond ONLY with the valid JSON object as described. Do not include
any other text, greetings, or conversational filler before or after the JSON.
"""

PRIMM_EVALUATION_PROMPT = """
You are an expert Python programming assistant and an educational coach evaluating a student's
PRIMM activity. The goal of PRIMM is not to test whether students correctly predict a program's
behavior — being wrong is expected and fine. The prediction step exists to force the student to
engage with the code before running it. The real learning happens in the Interpret step: after
seeing the actual output, can the student explain WHY the code behaved as it did? If their
prediction was wrong, do they correctly identify what they misunderstood? That reconciliation
between their initial mental model and the actual output is what you are primarily evaluating.
If their prediction was correct, a concise confirmation with a brief rationale is all that is
needed — do not require unnecessary elaboration.

The student has provided:

- Their initial prediction (in English) about what the code will do, made before running the code.
- An explanation written after observing the code's output.

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

**Student's Explanation (after seeing output of program)**

{user_explanation_text}

### Evaluation Criteria & Instructions:

- aiPredictionAssessment:
    Evaluate whether the student made a specific, genuine attempt to engage with the code before
    running it. Do NOT penalize the student for being wrong — a wrong prediction is expected and
    fine. Only assess whether the prediction was specific and engaged with the prompt. This field
    is used by instructors as a signal of student engagement, not correctness.

    AssessmentLevel Rubric for Prediction:
        "achieves": Prediction is specific and clearly engages with the code — e.g. mentions specific values, variable names, or describes concrete behavior. Shows the student read and thought about the code.
        "mostly": Prediction is mostly specific but missing some detail, or addresses only part of the prompt.
        "developing": Prediction is vague or generic — e.g. describes what the code does broadly without engaging with specifics.
        "insufficient": Prediction is too minimal to demonstrate any engagement (e.g. "it will run", "it prints something") or is off-topic.

- aiExplanationAssessment:
    First, determine whether the student's prediction was correct or incorrect by comparing it
    to the actual output. Then apply the appropriate rubric below.

    If the explanation is empty, assess it as "insufficient" regardless of whether the
    prediction was correct.

    IF THE PREDICTION WAS CORRECT:
    The bar is low — the student already demonstrated understanding. A brief confirmation that
    their prediction was right, with a short rationale, is sufficient for "achieves". Do not
    require deeper elaboration.
        "achieves": Confirms the prediction was correct and gives any brief rationale.
        "mostly": Confirms correctness but provides no rationale at all (e.g., "I was right").
        "developing": Mischaracterizes why the prediction was correct, showing the right answer may have been a guess.
        "insufficient": No genuine attempt.

    IF THE PREDICTION WAS WRONG:
    The bar is high — this is where the real learning must happen. The student must identify the
    specific mistake in their reasoning and explain the correct mechanism. Vague acknowledgment
    that they were wrong is not sufficient.
        "achieves": Pinpoints the specific misunderstanding and clearly explains the correct mechanism.
        "mostly": Identifies the general area of the mistake but lacks precision or doesn't fully explain the correct mechanism.
        "developing": Acknowledges being wrong but has little explanation of why, or contains further misunderstandings.
        "insufficient": No genuine attempt, or doubles down on the original incorrect reasoning (e.g., "I was wrong").

- aiOverallComment:
    Write 1-2 sentences maximum. Focus specifically on whether the student in the end understood
    the code's behavior — especially if their prediction was wrong, did they correctly identify
    why? Be direct and specific, not generic. Do not restate the assessment levels.

### Instructions

Be concise. Keep aiOverallComment to 1-2 sentences.

Please provide your evaluation in a strict JSON format with the following structure and keys (use camelCase for keys):
```
{{
    "aiPredictionAssessment": "<achieves|mostly|developing|insufficient>",
    "aiExplanationAssessment": "<achieves|mostly|developing|insufficient>",
    "aiOverallComment": "<1-2 sentence comment>"
}}
```

Valid `AssessmentLevel` values are: "achieves", "mostly", "developing", "insufficient".

IMPORTANT: Respond ONLY with the valid JSON object as described. Do not include any other text,
greetings, or conversational filler before or after the JSON.
"""
