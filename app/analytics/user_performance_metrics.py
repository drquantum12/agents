from db_utility.mongo_db import mongo_db
from db_utility.firestore_db import student_metrics_collection, StudentBasicMetrics
from fastapi import APIRouter, Depends, HTTPException, status
from utility.auth import get_current_user_from_firebase_token
from collections import defaultdict

users_collection = mongo_db["users"]
quiz_collection = mongo_db["quizzes"]
quiz_submissions_collection = mongo_db["quiz_submissions"]



def updateStudentBasicMetricInDB(user_id: str) -> StudentBasicMetrics:
    """
    adds or updates student basic metrics in the database
    """
    try:
        # Materialize the cursor once
        quizzes_taken = list(
            quiz_submissions_collection.find(
                {"user_id": user_id},
                {"_id": 0, "quiz_id": 1, "is_correct": 1, "score": 1, "difficulty": 1, "subject": 1}
            )
        )

        if not quizzes_taken:
            # Optionally upsert an empty/default metrics doc here
            return {"message": "No quizzes taken by the user."}

        total_quizzes = len(quizzes_taken)
        total_score = sum(q.get("score", 0) for q in quizzes_taken)
        correct_count = sum(1 for q in quizzes_taken if q.get("is_correct", False))

        overall_accuracy = (correct_count / total_quizzes) * 100 if total_quizzes else 0.0
        average_score = (total_score / total_quizzes) if total_quizzes else 0.0

        # Aggregate subject-wise and difficulty-wise in Python
        subject_wise = defaultdict(lambda: {"total": 0, "correct": 0, "score": 0.0})
        difficulty_wise = defaultdict(lambda: {"total": 0, "correct": 0, "score": 0.0})

        for q in quizzes_taken:
            subj = q.get("subject", "Unknown")
            diff = q.get("difficulty", "easy")
            is_correct = 1 if q.get("is_correct", False) else 0
            sc = q.get("score", 0.0)

            subject_wise[subj]["total"] += 1
            subject_wise[subj]["correct"] += is_correct
            subject_wise[subj]["score"] += sc

            difficulty_wise[diff]["total"] += 1
            difficulty_wise[diff]["correct"] += is_correct
            difficulty_wise[diff]["score"] += sc

        subject_wise_accuracy = {
            s: (v["correct"] / v["total"]) * 100 if v["total"] else 0.0
            for s, v in subject_wise.items()
        }
        subject_wise_average_score = {
            s: (v["score"] / v["total"]) if v["total"] else 0.0
            for s, v in subject_wise.items()
        }
        difficulty_wise_accuracy = {
            d: (v["correct"] / v["total"]) * 100 if v["total"] else 0.0
            for d, v in difficulty_wise.items()
        }
        difficulty_wise_average_score = {
            d: (v["score"] / v["total"]) if v["total"] else 0.0
            for d, v in difficulty_wise.items()
        }

        student_metrics = StudentBasicMetrics(
            overall_accuracy=overall_accuracy,
            average_accuracy=overall_accuracy,  # or compute separately if needed
            average_score=average_score,
            subject_wise_accuracy=subject_wise_accuracy,
            subject_wise_average_score=subject_wise_average_score,
            quizzes_taken_count=total_quizzes,
            subject_wise_quizzes_taken_count={s: v["total"] for s, v in subject_wise.items()},
            difficulty_wise_accuracy=difficulty_wise_accuracy,
            difficulty_wise_average_score=difficulty_wise_average_score,
            difficulty_wise_quizzes_taken_count={d: v["total"] for d, v in difficulty_wise.items()},
        )

        # Persist metrics (ensure this method accepts your model/dict)
        student_metrics_collection.add_or_update_document(user_id, student_metrics)

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
        user_metrics = student_metrics_collection.get_document(user_id)
        if not user_metrics:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User metrics not found")

        return user_metrics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user performance metrics: {str(e)}",
        )