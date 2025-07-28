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
quiz_performance_collection = mongo_db["quiz_performance"]


def save_quiz(quiz_data: dict, user_id: str) -> str:
    """
    Save a quiz to the MongoDB collection.
    
    :param quiz_data: A dictionary containing quiz data.
    :return: The ID of the saved quiz document.
    """
    quiz_data["_id"] = str(uuid4())  # Generate a unique ID for the quiz
    quiz_data["created_at"] = datetime.now()

    result = quiz_collection.insert_one(quiz_data)

     # adding quiz ID to user's quiz_ids array
    users_collection.update_one(
        {"_id": user_id},
        {"$push": {"quiz_ids": {"_id": quiz_data["_id"]}}}
    )
    if not result.acknowledged:
        raise Exception("Failed to save quiz to the database")
    return quiz_data

@quiz_router.post("/save-user-quiz-result")
async def save_user_quiz_result(quiz_result: dict, user: str = Depends(get_current_user_from_firebase_token)):
    """
    Save the user's quiz result.
    quiz_result : {
        "quiz_id": str,
        "is_correct": bool,
        "selected_option: str,
        "difficulty": str,
        "subject": str
    }
    """
    try:
        # Validate and process the quiz result
        validated_result = QuizResult(**quiz_result, user_id=user["user_id"], responded_at=datetime.now())
        if validated_result["is_correct"]:
            validated_result["score"] = difficulty_level_score_mapping.get(validated_result.get("difficulty", "easy"), 1)
        else:   
            validated_result["score"] = 0

        user_id = validated_result["user_id"]
        quiz_id = validated_result["quiz_id"]
        update_result = users_collection.update_one(
            {
                "_id": user_id,
                "quiz_ids._id": quiz_id
            },
            {"$set": {"quiz_ids.$[quiz].is_correct": validated_result["is_correct"],
                      "quiz_ids.$[quiz].selected_option": validated_result["selected_option"],
                      "quiz_ids.$[quiz].score": validated_result["score"],
                      "quiz_ids.$[quiz].responded_at": validated_result["responded_at"]
                      }},
            array_filters=[{"quiz._id": quiz_id}]
        )

        # if no quiz matched, push new quiz_id document
        if update_result.matched_count == 0:
            users_collection.update_one(
                {"_id": user_id},
                {"$push": {"quiz_ids": {
                    "_id": quiz_id,
                    "is_correct": validated_result["is_correct"],
                    "selected_option": validated_result["selected_option"],
                    "score": validated_result["score"],
                    "responded_at": validated_result["responded_at"]
                }}}
            )

        # update student basic metrics after quiz response
        updateStudentBasicMetricInDB(user_id)

        return {"message": "Quiz result saved successfully", "quiz_id": quiz_id}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))