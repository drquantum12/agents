import re

def extract_mcq(md_text):
    # Extract question
    question_match = re.search(r'### Question:\s*(.+)', md_text)
    question = question_match.group(1).strip() if question_match else None

    # Extract options: handles "**A.** option" and trims markdown
    options_matches = re.findall(r'\*\*(A|B|C|D)\.\*\*\s*(.+)', md_text)
    options = {key: value.strip() for key, value in options_matches}

    # Extract correct answer: matches both "B" and "B." and strips punctuation
    correct_match = re.search(r'\*\*Correct Answer:\*\*\s*([A-D])\.?', md_text)
    correct_answer = correct_match.group(1).strip() if correct_match else None

    # Extract explanation (handles trailing period and multiple lines)
    explanation_match = re.search(r'\*\*Explanation:\*\*\s*(.+)', md_text, re.DOTALL)
    explanation = explanation_match.group(1).strip() if explanation_match else None

    # Extract difficulty level
    difficulty_match = re.search(r'\*\*Difficulty:\*\*\s*(easy|medium|hard)', md_text, re.IGNORECASE)
    difficulty = difficulty_match.group(1).strip() if difficulty_match else None

    return {
        "question": question,
        "options": options,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "difficulty": difficulty
    }