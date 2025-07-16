from db_utility.mongo_db import mongo_db
from uuid import uuid4
from datetime import datetime

quiz_collection = mongo_db["quizzes"]
users_collection = mongo_db["users"]


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