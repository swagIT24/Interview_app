import asyncio
import json
import logging
from services.llm_service import client

logger = logging.getLogger(__name__)

# ── Call 1: honest critical analysis (plain text, temp=0.3) ──────────────────

_ANALYSIS_SYSTEM = """You are a brutal but fair senior technical interviewer at a top tech company.
You have seen thousands of interview answers. Your job is to analyse this \
answer honestly — not to encourage the candidate.

Write a critical analysis covering ALL of these:

WHAT THEY GOT RIGHT:
- List only things that are genuinely correct and complete
- Be specific, not generic ("correctly explained X" not "good answer")

WHAT WAS WEAK OR MISSING:
- List every gap, vague claim, or missing concept
- If they listed techniques without explaining tradeoffs, say so explicitly
- If their example was generic or lacked numbers/outcomes, say so
- If they missed an important concept the question required, name it

DEPTH ASSESSMENT:
- Did they explain WHY, not just WHAT?
- Did they mention tradeoffs, edge cases, or failure modes?
- Or did they just list things?

EXAMPLE QUALITY:
- Was the example specific with real numbers or outcomes?
- Or was it vague and could apply to any project?

ONE KEY THING MISSING:
- The single most important concept or detail they skipped
- If nothing is missing, say "none"

Be direct. Do not soften criticism. Do not say "great answer."
If the answer is genuinely strong and complete, acknowledge it honestly. Do not invent weaknesses that are not there. A strong answer deserves a strong score.
"""

# ── Call 2: score based on the analysis (JSON, temp=0.1) ─────────────────────

_SCORING_SYSTEM = """You are a precise scoring engine. You will be given:
1. An interview question
2. A candidate's answer
3. A critical analysis written by a senior interviewer

Your job is to translate that analysis into scores.
The scores MUST be consistent with the analysis.
If the analysis says something was weak, that dimension cannot be 2/2.
If the analysis says something was missing, missed_key_point cannot be null.

Score on EXACTLY these 5 dimensions, each 0-2:

CORRECTNESS (0-2):
  2 = everything said was factually accurate and complete
  1 = mostly correct, minor errors or omissions
  0 = factually wrong or completely off topic

DEPTH (0-2):
  2 = explained WHY, mentioned tradeoffs, edge cases, or failure modes
  1 = explained WHAT but not WHY, no tradeoffs mentioned
  0 = surface level, buzzwords only

CLARITY (0-2):
  2 = well structured, easy to follow, logical flow
  1 = understandable but could be more structured
  0 = rambling, hard to follow

EXAMPLES (0-2):
  2 = specific real example with actual numbers, outcomes, or named project details
  1 = example given but vague or generic
  0 = no example given at all

COMPLETENESS (0-2):
  2 = fully answered everything the question asked
  1 = covered main points but missed something the question explicitly asked
  0 = missed major parts of the question

SCORING RULES — these are absolute:
- If the analysis mentions ANY weakness in a dimension → that dimension is 1 or 0, never 2
- If the analysis says "lacked tradeoffs" → depth is 1 or 0
- If the analysis says "example was vague" → examples is 1 or 0
- If the analysis says "one key thing missing" is not "none" → missed_key_point is not null
- Total = sum of all 5 dimensions (max 10)
- 10/10 is only possible if the analysis found zero weaknesses
- good_answer_example is REQUIRED and must never be null or empty.

Return ONLY valid JSON, nothing else:
{
  "scores": {
    "correctness": <0-2>,
    "depth": <0-2>,
    "clarity": <0-2>,
    "examples": <0-2>,
    "completeness": <0-2>
  },
  "total": <0-10>,
  "strongest_dimension": "<dimension name>",
  "weakest_dimension": "<dimension name or null if all 2/2>",
  "one_line_verdict": "<max 12 words describing this answer>",
  "missed_key_point": "<what they skipped, or null if nothing missing>",
  "good_answer_example": "<REQUIRED — write a complete 3-4 sentence ideal answer to this question covering definition, explanation, real example, and tradeoffs. Never return null for this field.>"
}
"""

# ── Call 3: coaching prose (called separately via generate_feedback) ──────────

_FEEDBACK_SYSTEM = """You are a direct, no-nonsense senior engineering coach reviewing a candidate's interview answer.

Write EXACTLY 2 sentences. No more. No exceptions.
Sentence 1: What they got right + the core gap in one sentence.
Sentence 2: One specific thing to practice this week.

Hard rules:
- NEVER open with "Great answer!", "Well done!", or any generic praise
- ALWAYS name the specific concept or technique that was missed
- Tone: honest coach who wants them to succeed, not a cheerleader
- 2 sentences maximum — if you write more you have failed the task"""


async def evaluate_answer(question: str, answer: str, difficulty: str = "intermediate") -> dict:
    """
    Two-call chain-of-thought evaluation.

    Call 1 → honest critical analysis (plain text).
    Call 2 → scores derived from that analysis (JSON).

    Returns the standard result dict plus "analysis_text" for downstream use.
    """
    # ── Call 1: critical analysis ─────────────────────────────────────────────
    try:
        resp1 = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _ANALYSIS_SYSTEM},
                {"role": "user",   "content": (
                    f"Question: {question}\n"
                    f"Difficulty: {difficulty}\n"
                    f"Candidate's answer: {answer}\n\n"
                    "Write your critical analysis now."
                )},
            ],
            temperature=0.3,
        )
        analysis_text = resp1.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"evaluate_answer Call 1 failed: {e}")
        raise

    # ── Call 2: score based on the analysis ───────────────────────────────────
    try:
        resp2 = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SCORING_SYSTEM},
                {"role": "user",   "content": (
                    f"Question: {question}\n"
                    f"Difficulty: {difficulty}\n"
                    f"Candidate's answer: {answer}\n\n"
                    f"Critical analysis from senior interviewer:\n{analysis_text}\n\n"
                    "Now score based on this analysis. Remember: scores must match the analysis."
                )},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        result = json.loads(resp2.choices[0].message.content)
    except Exception as e:
        logger.error(f"evaluate_answer Call 2 failed: {e}")
        raise

    scores = result.get("scores", {})
    total  = result.get("total", sum(scores.values()) if scores else 0)

    # Difficulty bonus: advanced answers clearing 7/10 get +1 (cap 10)
    if difficulty == "advanced" and total >= 7:
        total = min(total + 1, 10)

    result["total"]  = total
    result["scores"] = scores
    result.setdefault("strongest_dimension", max(scores, key=scores.get) if scores else "clarity")
    result.setdefault("weakest_dimension",   min(scores, key=scores.get) if scores else "depth")
    result.setdefault("one_line_verdict",    "Answer needs more depth and specifics.")
    result.setdefault("missed_key_point",    None)
    result["good_answer_example"] = result.get("good_answer_example") or result.get("model_answer_hint") or ""
    if not result.get("good_answer_example"):
        result["good_answer_example"] = f"A strong answer would cover: {result.get('missed_key_point', '')}. Focus on definition, real examples, and tradeoffs."

    # When every dimension is 2/2 there is no meaningful "weakest"
    all_max = scores and all(v == 2 for v in scores.values())
    if all_max:
        result["weakest_dimension"] = None
        result["missed_key_point"]  = None
    else:
        result["weakest_dimension"] = min(scores, key=scores.get) if scores else "depth"

    result["analysis_text"] = analysis_text
    return result


async def generate_feedback(question: str, answer: str, score_result: dict,
                             difficulty: str = "intermediate",
                             analysis_text: str = "") -> str:
    """
    Generate direct coaching prose grounded in the critical analysis.
    Returns a feedback string (3-5 sentences, no bullets).
    """
    weakest = score_result.get("weakest_dimension", "depth")
    missed  = score_result.get("missed_key_point") or "not identified"
    hint    = score_result.get("good_answer_example", "")
    total   = score_result.get("total", 0)

    analysis_section = (
        f"\nSenior interviewer's analysis:\n{analysis_text}\n\n"
        "Use this analysis to make the feedback specific and accurate."
        if analysis_text else ""
    )

    user_content = (
        f"Question: {question}\n\n"
        f"Candidate Answer: {answer}\n\n"
        f"Score: {total}/10 | Difficulty: {difficulty}\n"
        f"Weakest dimension: {weakest}\n"
        f"Missed key point: {missed}\n"
        f"What a top answer looks like: {hint}"
        f"{analysis_section}\n\n"
        "Write the coaching feedback now."
    )

    try:
        resp = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _FEEDBACK_SYSTEM},
                {"role": "user",   "content": user_content},
            ],
            temperature=0.4,
        )
        return resp.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"generate_feedback failed: {e}")
        return (
            f"Score: {total}/10. Your {weakest} needs work — "
            f"focus on including specific real-world examples and discussing tradeoffs next time."
        )
