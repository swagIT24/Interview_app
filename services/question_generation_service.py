from services.llm_service import client


def generate_question(domain, previous_questions=None):

    if previous_questions is None:
        previous_questions = []
    print("PREVIOUS QUESTIONS:", previous_questions)
    prompt = f"""
You are a professional technical interviewer conducting a real interview.

Your task is to generate EXACTLY ONE interview question.

INTERVIEW CONTEXT:
- Domain: {domain}

PREVIOUSLY ASKED QUESTIONS:
{previous_questions}

STRICT RULES:
1. Generate ONLY ONE question.
2. Do NOT repeat or closely resemble any previous question.
3. Avoid asking about the same concept/subtopic again.
4. Question must match the difficulty level.
5. Keep the question realistic and interview-quality.
6. No explanations.
7. No answers.
8. No numbering.
9. No greetings or extra text.
10. Return ONLY the raw question text.

QUESTION QUALITY RULES:
- The question should test understanding, not trivia.
- Prefer practical and conceptual interview questions.
- Keep question concise and clear.
- Avoid overly broad questions.
- Avoid duplicate phrasing patterns.

EXAMPLE BAD OUTPUT:
"1. What is Python?"
"Here is your question:"
"Explain Python in detail."

EXAMPLE GOOD OUTPUT:
"What is the difference between a list and tuple in Python?"
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    question = response.choices[0].message.content.strip()

    question = question.replace("\\n", "\n")
    question = question.replace("```python", "")
    question = question.replace("```", "")
    question = question.replace('"', "")

    return question.strip()
