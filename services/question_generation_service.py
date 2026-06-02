import json
import logging
from services.llm_service import client

logger = logging.getLogger(__name__)


def _extract_resume_signals(resume_text: str) -> str:
    """Summarise a resume into one sentence via LLM — avoids dumping raw text into every prompt."""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": (
                    "Extract in one sentence: years of experience, key technologies used, "
                    f"most notable project. Resume:\n{resume_text[:2000]}"
                ),
            }],
            temperature=0.1,
            max_tokens=80,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"_extract_resume_signals failed: {e}")
        return ""


def _adaptive_difficulty(session_history: list) -> tuple[str, str]:
    """Return (difficulty_label, interviewer_instruction) based on recent scores."""
    scores = [s for s in (session_history or []) if isinstance(s, (int, float))]
    if not scores:
        return "intermediate", "Test understanding, not memorisation"
    avg = sum(scores) / len(scores)
    if avg >= 7.5:
        return "advanced",     "Push harder — edge cases, failure modes, tradeoffs"
    if avg <= 4.5:
        return "beginner",     "Step back to fundamentals"
    return     "intermediate", "Test understanding, not memorisation"


def generate_question(
    domain=None,
    asked_questions=None,
    resume_text=None,
    profile=None,
    session_history=None,
    topic=None,
) -> dict:
    """
    Generate one interview question.

    Backward-compatible call: generate_question(domain, asked_questions, resume_text)
    Enhanced call:            generate_question(domain, session_history=[...], profile={...})

    Returns a dict:
    {
        "question":                    str,
        "difficulty":                  str,
        "what_a_good_answer_covers":   [str, str, str],
        "follow_up_if_answer_is_shallow": str,
    }
    """
    if asked_questions is None:
        asked_questions = []

    effective_domain = topic or domain or "Software Engineering"
    difficulty, difficulty_instruction = _adaptive_difficulty(session_history)

    # Resume: extract signals, don't dump raw text
    resume_signal = ""
    if resume_text:
        resume_signal = _extract_resume_signals(resume_text)

    # Profile context
    profile_lines = []
    if profile and isinstance(profile, dict):
        if profile.get("target_role"):
            profile_lines.append(f"Target role: {profile['target_role']}")
        if profile.get("weak_areas"):
            profile_lines.append(f"Weak areas to probe: {profile['weak_areas']}")
    profile_context = "\n".join(profile_lines)

    already_asked = (
        "\n".join(f"- {q}" for q in asked_questions)
        if asked_questions else "None yet"
    )

    system_prompt = f"""You are a senior interviewer at a top tech company running a {difficulty}-level interview.

Difficulty: {difficulty.upper()} — {difficulty_instruction}

Candidate background: {resume_signal or 'Not provided'}
{profile_context}

Generate ONE interview question that:
- Is strictly about: {effective_domain}
- Has NOT been asked before (see already-asked list below)
- Matches {difficulty} difficulty exactly
- References the candidate's background where naturally relevant (e.g. "You've used X — how would you...")
- Can be answered verbally in 2-4 minutes
- Tests real understanding, not trivia or memorisation

Already asked:
{already_asked}

Return ONLY valid JSON, nothing else:
{{
  "question": "the full question text",
  "difficulty": "{difficulty}",
  "what_a_good_answer_covers": ["key point 1", "key point 2", "key point 3"],
  "follow_up_if_answer_is_shallow": "a sharper follow-up question"
}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": system_prompt}],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        result.setdefault("difficulty", difficulty)
        result.setdefault("what_a_good_answer_covers", [])
        result.setdefault("follow_up_if_answer_is_shallow", "")
        return result

    except Exception as e:
        logger.error(f"generate_question failed: {e}")
        fallback = f"Can you explain a key concept in {effective_domain} and describe a real-world scenario where you applied it?"
        return {
            "question": fallback,
            "difficulty": difficulty,
            "what_a_good_answer_covers": [],
            "follow_up_if_answer_is_shallow": "Can you walk me through a specific example?",
        }
