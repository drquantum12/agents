from db_utility.mongo_db import mongo_db
from uuid import uuid4
from datetime import datetime
from fastapi import HTTPException, status, Depends, APIRouter
from utility.auth import get_current_user_from_firebase_token
from typing import TypedDict

class QuizResult(TypedDict):
    quiz_id: str
    user_id: str
    is_correct: bool
    score: float
    difficulty: str
    created_at: datetime

quiz_router = APIRouter(
    responses={404: {"description": "Not found"}},
)

quiz_collection = mongo_db["quizzes"]
users_collection = mongo_db["users"]
quiz_performance_collection = mongo_db["quiz_performance"]


def save_quiz(quiz_data: dict, user_id: str) -> str:
    """
    Save a quiz to the MongoDB collection.
    
    :param quiz_data: A dictionary containing quiz data.
    :return: The ID of the saved quiz document.
    """
    quiz_data["_id"] = str(uuid4())  # Generate a unique ID for the quiz
    quiz_data["user_id"] = user_id
    quiz_data["created_at"] = datetime.now()

    result = quiz_collection.insert_one(quiz_data)

     # adding quiz ID to user's quiz_ids array
    users_collection.update_one(
        {"_id": user_id},
        {"$push": {"quiz_ids": {"_id": quiz_data["_id"], "created_at": quiz_data["created_at"]}}}
    )
    if not result.acknowledged:
        raise Exception("Failed to save quiz to the database")
    return quiz_data

@quiz_router.post("/save-user-quiz-result")
async def save_user_quiz_result(quiz_result: dict, user_id: str = Depends(get_current_user_from_firebase_token)):
    """
    Save the user's quiz result.
    quiz_result : {
        "quiz_id": str,
        "is_correct": bool,
        "score": float,
        "difficulty": str
    }
    """
    try:
        # Validate and process the quiz result
        validated_result = QuizResult(**quiz_result, user_id=user_id, created_at=datetime.now())
        quiz_performance_collection.insert_one(validated_result)
        return {"message": "Quiz result saved successfully", "quiz_id": validated_result["quiz_id"]}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))