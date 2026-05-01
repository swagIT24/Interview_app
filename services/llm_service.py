from dotenv import load_dotenv
import os
import json
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def evaluate_with_llm(question: str, answer: str):
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

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        content = response.choices[0].message.content

        try:
            result = json.loads(content)

            score = result["score"]

            feedback = f"""
        Strengths: {result['strengths']}

        Weaknesses: {result['weaknesses']}

        Improve: {result['improvement']}
        """

            return score, feedback

        except Exception as e:
            print("Parsing ERROR:", e)
            return 5, "Could not evaluate properly"

    except Exception as e:
        print("LLM ERROR:", e)
        return 5, "Default evaluation (LLM failed)"