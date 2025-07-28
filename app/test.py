# from db_utility.vector_db import VectorDB

# vector_db = VectorDB()
from db_utility.mongo_db import mongo_db
from datetime import datetime
from utility.quizzes import QuizResult, difficulty_level_score_mapping

users_collection = mongo_db["users"]
quiz_collection = mongo_db["quizzes"]
user_id = "ptLFqq0N9JTyYL7lkAqhB1YSFj32"

# quiz_result = {"quiz_id": "fa4613a7-dbef-470f-8021-8c51f793cdb2", "is_correct": False, "selected_option": "C", "subject": "Science", "difficulty": "easy"}

def user_metrics(user_id: str):
    """
    Return : overall accuracy, average accuracy, average score, subject-wise accuracy,
    subject-wise average score, quizzes taken count, subject-wise quizzes taken count
    """
    try:
        quizzes_taken = users_collection.find_one({"_id": user_id}, {"quiz_ids": 1})
        if not quizzes_taken or not quizzes_taken.get("quiz_ids", []):
            return {"message": "No quizzes taken by the user."}
        quiz_ids = quizzes_taken["quiz_ids"]
        total_quizzes = len(quiz_ids)
        total_score = sum(quiz["score"] for quiz in quiz_ids if "score" in quiz)

        overall_accuracy = sum(quiz["is_correct"] for quiz in quiz_ids) / total_quizzes * 100
        average_score = total_score / total_quizzes if total_quizzes > 0 else 0

        # get subject and difficulty for quiz_ids from quizzes collection
        quizzes = quiz_collection.find({"_id": {"$in": [quiz["_id"] for quiz in quiz_ids]}}, {"subject": 1, "difficulty": 1})
        subject_difficulty_map = {quiz["_id"]: (quiz["subject"], quiz["difficulty"]) for quiz in quizzes}
        # Calculate subject-wise accuracy, average score and difficulty-wise accuracy and average score
        subject_wise_data = {}
        difficulty_wise_data = {}
        for quiz in quiz_ids:
            subject, difficulty = subject_difficulty_map.get(quiz["_id"], ("Unknown", "easy"))
            if subject not in subject_wise_data:
                subject_wise_data[subject] = {"total": 0, "correct": 0, "score": 0}
            if difficulty not in difficulty_wise_data:
                difficulty_wise_data[difficulty] = {"total": 0, "correct": 0, "score": 0}
            subject_wise_data[subject]["total"] += 1
            subject_wise_data[subject]["correct"] += quiz.get("is_correct", 0)
            subject_wise_data[subject]["score"] += quiz.get("score", 0)
            difficulty_wise_data[difficulty]["total"] += 1
            difficulty_wise_data[difficulty]["correct"] += quiz.get("is_correct", 0)
            difficulty_wise_data[difficulty]["score"] += quiz.get("score", 0)
        subject_wise_accuracy = {subj: data["correct"] / data["total"] * 100 for subj, data in subject_wise_data.items()}
        subject_wise_average_score = {subj: data["score"] / data["total"] for subj, data in subject_wise_data.items()}
        difficulty_wise_accuracy = {diff: data["correct"] / data["total"] * 100 for diff, data in difficulty_wise_data.items()}
        difficulty_wise_average_score = {diff: data["score"] / data["total"] for diff, data in difficulty_wise_data.items()}
        return {
            "overall_accuracy": overall_accuracy,
            "average_accuracy": overall_accuracy,
            "average_score": average_score,
            "subject_wise_accuracy": subject_wise_accuracy,
            "subject_wise_average_score": subject_wise_average_score,
            "quizzes_taken_count": total_quizzes,
            "subject_wise_quizzes_taken_count": {subj: data["total"] for subj, data in subject_wise_data.items()},
            "difficulty_wise_accuracy": difficulty_wise_accuracy,
            "difficulty_wise_average_score": difficulty_wise_average_score,
            "difficulty_wise_quizzes_taken_count": {diff: data["total"] for diff, data in difficulty_wise_data.items()},
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    basic_metrics = user_metrics(user_id)
