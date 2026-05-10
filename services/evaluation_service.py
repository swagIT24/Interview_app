import json
from services.llm_service import call_llm
import re

def extract_json(text: str):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    else:
        raise ValueError("No JSON found")

def evaluate_answer(question: str, answer: str):
    try:
        prompt = f"""
You are a senior technical interviewer and honest mentor.
You evaluate answers exactly as a real interviewer would —
strictly on what was actually said, not on potential or intent.
Your feedback is direct, specific, and constructive.
You never sugarcoat a weak answer but you always show the
candidate exactly how to improve.

Question:
{question}

Candidate Answer:
{answer}

SCORING GUIDE — follow this exactly, no exceptions:
0-3:  Incomplete, cut off mid-sentence, off topic,
      single vague sentence, or shows no understanding.
      → If answer is unfinished: maximum 2, always.

4-6:  Basic definition only. No depth, no examples,
      no types or variants mentioned, no real world use.
      This answer would fail a real interview.
      Shows the candidate has surface knowledge only.

7-9:  Decent answer. Has definition PLUS at least one
      of the following: example, types, real world use.
      Would pass screening but would not impress.
      Still missing depth or structure.

10-12: Strong answer. Well structured, clear examples,
       mentions types or variants, real world application.
       Would impress most interviewers.
       Minor gaps only.

13-15: Exceptional. Covers definition, types, examples,
       real world application, and shows deep understanding.
       Exactly what a senior interviewer wants to hear.
       Rare — only for truly complete answers.

STRICT SCORING RULES — apply every single time:
- Unfinished or cut off answer → maximum 2, no exceptions
- One or two sentences only → maximum 4, no exceptions
- No concrete example given → cannot score above 7
- No depth beyond surface definition → cannot score above 5
- No types or variants mentioned → cannot score above 8
- Evaluate ONLY what is written — not what they meant to say
- Do NOT reward intent, effort, or partial thoughts
- A mediocre answer that sounds confident is still mediocre
- When in doubt, score lower — it helps them more

WEAKNESS RULES — be specific and direct:
- Always list at least 2 specific weaknesses
- Name exactly what is missing — do not be vague
- Bad example: "needs more depth"
- Good example: "did not mention any types of regression
  such as linear, logistic or polynomial"
- Good example: "no real world example was provided —
  e.g. predicting house prices using linear regression"
- Good example: "answer was cut off and never completed"
- The weakness section should be the most detailed section

TONE RULES:
- Strengths: find something genuine — even small things count
  but do not invent strengths that are not there
- Weaknesses: direct and specific — name exactly what is missing
- Tip: give ONE actionable thing they can do right now
- Example: show a complete strong answer so they see the standard
- Overall tone: honest mentor, not a cheerleader, not a bully

IMPORTANT:
- Return ONLY valid JSON
- Do NOT add any explanation before or after
- Do NOT add text like "Here is the result"
- Output must start with {{ and end with }}

JSON FORMAT:
{{
    "score": int,
    "strengths": "string",
    "weaknesses": "string",
    "improvement": "string",
    "example": "string"
}}
        """

        content = call_llm(prompt)

    except Exception as e:
        print("LLM ERROR:", e)
        return {
            "score": 5,
            "feedback": "Evaluation failed due to system issue. Please try again."
        }

    try:
        result = extract_json(content)

        score = result.get("score", 5)

        feedback = (
            f"Strengths: {result.get('strengths', 'You attempted the question.')}\n\n"
            f"Weaknesses: {result.get('weaknesses', 'Answer lacks depth and specific details.')}\n\n"
            f"Tip: {result.get('improvement', 'Structure your answer with definition, types, and a real world example.')}\n\n"
            f"Example: {result.get('example', '')}"
        )

        return {
            "score": score,
            "feedback": feedback
        }

    except Exception as e:
        print("Parsing ERROR:", e)
        return {
            "score": 5,
            "feedback": "Could not process evaluation. Please try again."
        }