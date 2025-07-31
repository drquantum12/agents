from db_utility.mongo_db import mongo_db
from uuid import uuid4
from datetime import datetime
from fastapi import HTTPException, status, Depends, APIRouter
from utility.auth import get_current_user_from_firebase_token
from typing_extensions import Literal, TypedDict
from analytics.user_performance_metrics import updateStudentBasicMetricInDB

class QuizResult(TypedDict):
    quiz_id: str
    user_id: str
    is_correct: bool
    selected_option: str
    score: float
    difficulty: Literal["easy", "medium", "hard"]
    subject: str
    responded_at: datetime

difficulty_level_score_mapping = {
    "easy": 1,
    "medium": 2,
    "hard": 3
}

quiz_router = APIRouter(
    responses={404: {"description": "Not found"}},
)

quiz_collection = mongo_db["quizzes"]
users_collection = mongo_db["users"]
quiz_submissions_collection = mongo_db["quiz_submissions"]


def save_quiz(quiz_data: dict) -> str:
    """
    Save a quiz to the MongoDB collection.
    
    :param quiz_data: A dictionary containing quiz data.
    :return: The ID of the saved quiz document.
    """
    quiz_data["_id"] = str(uuid4())  # Generate a unique ID for the quiz
    quiz_data["created_at"] = datetime.now()

    result = quiz_collection.insert_one(quiz_data)

    if not result.acknowledged:
        raise Exception("Failed to save quiz to the database")
    return quiz_data

@quiz_router.post("/save-user-quiz-result")
async def save_user_quiz_result(quiz_result: dict, user: dict = Depends(get_current_user_from_firebase_token)):
    try:
        # Validate + build plain dict
        validated = QuizResult(**quiz_result, user_id=user["user_id"], responded_at=datetime.utcnow())
        doc = validated.model_dump() if hasattr(validated, "model_dump") else dict(validated)

        # compute score
        doc["score"] = difficulty_level_score_mapping.get(doc.get("difficulty", "easy"), 1) if doc.get("is_correct") else 0

        user_id = doc["user_id"]
        quiz_id = doc["quiz_id"]

        # Upsert on (user_id, quiz_id)
        result = quiz_submissions_collection.update_one(
            {"user_id": user_id, "quiz_id": quiz_id},
            {
                "$set": {
                    "is_correct": doc["is_correct"],
                    "selected_option": doc.get("selected_option"),
                    "score": doc["score"],
                    "difficulty": doc.get("difficulty"),
                    "subject": doc.get("subject"),
                    "responded_at": doc["responded_at"],
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "quiz_id": quiz_id,
                    "created_at": datetime.now(),
                },
            },
            upsert=True,
        )

        # Update user's last submission time after successful upsert
        users_collection.update_one(
            {"_id": user_id},
            {"$set": {"last_quiz_submission_time": datetime.now()}}
        )

        # Recompute metrics after DB is updated
        updateStudentBasicMetricInDB(user_id)

        status = "created" if result.upserted_id is not None else "updated"
        return {"message": f"Quiz result {status} successfully", "quiz_id": quiz_id}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))