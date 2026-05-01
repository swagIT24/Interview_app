
import json
from services.llm_service import call_llm

def evaluate_answer(question: str, answer: str):
    try:
        prompt = f"""
        You are a senior technical interviewer.

        Question:
        {question}

        Candidate Answer:
        {answer}

        Evaluate the answer strictly.

        Return ONLY JSON:

        {{
            "score": int,
            "strengths": "what was good",
            "weaknesses": "what is missing or wrong",
            "improvement": "how to improve answer"
        }}
        """

        content = call_llm(prompt)

    except Exception as e:
        print("LLM ERROR:", e)
        return 5, "Evaluation failed due to system issue. Please try again."

    try:
        result = json.loads(content)

        score = result.get("score", 5)

        feedback = f"""
        Strengths: {result.get('strengths', 'No clear strengths identified.')}

        Weaknesses: {result.get('weaknesses', 'No specific weaknesses identified.')}

        Improve: {result.get('improvement', 'Try to structure your answer more clearly and include relevant details.')}
        """

        return {
            "score": score,
            "feedback": feedback
        }

    except Exception as e:
        print("Parsing ERROR:", e)
        return 5, "Could not process evaluation properly. Please try again."