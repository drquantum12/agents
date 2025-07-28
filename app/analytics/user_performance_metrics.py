from db_utility.mongo_db import mongo_db
from typing_extensions import TypedDict
from fastapi import APIRouter, Depends, HTTPException, status
from utility.auth import get_current_user_from_firebase_token

users_collection = mongo_db["users"]
quiz_collection = mongo_db["quizzes"]
student_metrics_collection = mongo_db["student_metrics"]

class StudentBasicMetrics(TypedDict):
    overall_accuracy: float
    average_accuracy: float
    average_score: float
    subject_wise_accuracy: dict[str, float]
    subject_wise_average_score: dict[str, float]
    quizzes_taken_count: int
    subject_wise_quizzes_taken_count: dict[str, int]
    difficulty_wise_accuracy: dict[str, float]
    difficulty_wise_average_score: dict[str, float]
    difficulty_wise_quizzes_taken_count: dict[str, int]

class StudentIntellectualLevelMetrics(TypedDict):
    knowledge_mastery: str
    challenge_preference: str
    conceptual_stability: str
    learning_engagement: str
    peak_learning_hours: int
    adaptation_strategy: str

def updateStudentBasicMetricInDB(user_id: str) -> StudentBasicMetrics:
    """
    adds or updates student basic metrics in the database
    :param user_id: str
    :return: StudentBasicMetrics
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
        student_metrics = StudentBasicMetrics(
            overall_accuracy=overall_accuracy,
            average_accuracy=overall_accuracy,
            average_score=average_score,
            subject_wise_accuracy=subject_wise_accuracy,
            subject_wise_average_score=subject_wise_average_score,
            quizzes_taken_count=total_quizzes,
            subject_wise_quizzes_taken_count={subj: data["total"] for subj, data in subject_wise_data.items()},
            difficulty_wise_accuracy=difficulty_wise_accuracy,
            difficulty_wise_average_score=difficulty_wise_average_score,
            difficulty_wise_quizzes_taken_count={diff: data["total"] for diff, data in difficulty_wise_data.items()},
        )
        # Update or insert the student metrics in the database
        student_metrics_collection.update_one(
            {"_id": user_id},
            {"$set": student_metrics},
            upsert=True
        )
        return student_metrics
    except Exception as e:
        print(f"Error updating student metrics for user {user_id}: {str(e)}")
        return {"error": str(e)}

analytics_router = APIRouter(
    responses={404: {"description": "Not found"}},
)


@analytics_router.get("/user-performance/{user_id}", response_model=StudentBasicMetrics)
def get_user_performance(user_id: str, current_user: dict = Depends(get_current_user_from_firebase_token)):
    """
    Return : overall accuracy, average accuracy, average score, subject-wise accuracy,
    subject-wise average score, quizzes taken count, subject-wise quizzes taken count
    """
    try:
        user_metrics = student_metrics_collection.find_one({"_id": user_id})
        if not user_metrics:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User metrics not found")

        return user_metrics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user performance metrics: {str(e)}",
        )