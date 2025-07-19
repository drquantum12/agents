from fastapi import APIRouter, HTTPException, Header, Depends, status
from datetime import datetime
from pydantic import BaseModel
from utility.auth import get_current_user_from_firebase_token
from uuid import uuid4
from db_utility.mongo_db import mongo_db
from core_agents import build_agent, AgentState
from langchain_core.messages import AIMessageChunk
from utility.preprocessing import extract_mcq
from fastapi import WebSocket
from utility.quizzes import save_quiz
import os

class MessageSchema(BaseModel):
    role: str
    content: str

mongodb_user_collection = mongo_db["users"]
mongodb_session_collection = mongo_db["sessions"]
mongodb_quiz_collection = mongo_db["quizzes"]

chat_router = APIRouter(
    responses={404: {"description": "Not found"}},
)

def user_get_or_create_conversation_id(user_id: str):
    """
    Helper function to get or create a conversation ID for a user.
    """
    user_doc = mongodb_user_collection.find_one({"_id": user_id})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    conversation_ids = user_doc.get("conversation_ids", [])
    user_grade = user_doc.get("grade", "10th")  # Default to 10th grade if not specified
    if not conversation_ids:
        new_conversation_id = str(uuid4())
        mongodb_user_collection.update_one(
            {"_id": user_id},
            {"$push": {"conversation_ids": {"id": new_conversation_id, "created_at": datetime.now()}}}
        )
        return new_conversation_id, user_grade

    return conversation_ids[0]["id"], user_grade  # Return the first conversation ID and user grade if exists



@chat_router.post("/")
def chat(message: MessageSchema, current_user: dict = Depends(get_current_user_from_firebase_token)):

    # adding new coversation id to the list of conversation ids for the user

    new_conversation_id = str(uuid4())
    
    # adding new conversation id to conversation_ids array in user document
    mongodb_user_collection.update_one(
        {"_id": current_user["uid"]},
        {"$push": {"conversation_ids": {"id": new_conversation_id, "created_at": datetime.now()}}}
    )

    
    return {"message": "New conversation created", "conversation_id": new_conversation_id}

@chat_router.get("/conversations")
def get_conversations(current_user: dict = Depends(get_current_user_from_firebase_token)):
    """
    Get all conversations for the current user.
    """
    try:
        user_doc = mongodb_user_collection.find_one({"_id": current_user["uid"]})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        conversation_ids = user_doc.get("conversation_ids", [])
        return {"conversation_ids": conversation_ids}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving conversations: {str(e)}",
        )

# implementing lazy loading using limit and offset
@chat_router.get("/conversation/{conversation_id}")
def get_paginated_conversation(conversation_id: str, limit: int = 10, offset: int = 0, current_user: dict = Depends(get_current_user_from_firebase_token)):
    # Step 1: Get count only
    """
    Example response:
    {
        "conversation_id": "12345",
        "messages": [
            {"role": "human", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ],
        "total_messages": 100
    }
    """
    pipeline = [
        {"$match": {"_id": conversation_id}},
        {"$project": {"count": {"$size": "$messages"}}}
    ]
    result = list(mongodb_session_collection.aggregate(pipeline))

    if not result:
        raise HTTPException(status_code=404, detail="Conversation not found")

    total_messages = result[0]["count"]

    # Step 2: Compute proper slice
    start = max(total_messages - offset - limit, 0)
    slice_count = min(limit, total_messages - offset)

    # Step 3: Fetch just the required messages
    conversation_doc = mongodb_session_collection.find_one(
        {"_id": conversation_id},
        {"_id": 1, "messages": {"$slice": [start, slice_count]}}
    )

    messages = conversation_doc.get("messages", [])
    messages.reverse()  # Reverse to get latest messages first

    return {
        "conversation_id": conversation_id,
        "messages": messages,
        "total_messages": total_messages
    }


@chat_router.websocket("/ws/ai-tutor")
async def websocket_endpoint(websocket: WebSocket):

    user_id = websocket.query_params.get("user_id")
    conversation_id, user_grade = user_get_or_create_conversation_id(user_id)

    if not user_id or not conversation_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid user_id or conversation_id")
        return
    
    await websocket.accept()
    await websocket.send_json({"sender": "AI", "text": "Welcome to the AI Tutor!"})

    agent = build_agent()
    config = {"configurable": {"session_id": conversation_id}}

    while True:
        try:
            data = await websocket.receive_json()
            usr_msg = data.get("payload")
            print(f"Received message: {usr_msg}")

            state = AgentState(
                question=usr_msg,
                user_grade=user_grade,
                student_answer="",
                full_explanation="",
                messages=[],
                stage="start",
                retry_count=0,
                student_answers=[],
                hints_given=[],
                intent=""
            )
            generated_quiz = ""
            last_node = None

            for chunk, metadata in agent.stream(state, config=config, stream_mode="messages"):
                if isinstance(chunk, AIMessageChunk):
                    current_node = metadata.get("langgraph_node")

                    if current_node == "answering_node":
                        if last_node != current_node:
                            print("\n--- Answering Node ---\n")
                            last_node = current_node
                        # print(chunk.content, end="", flush=True)
                        await websocket.send_json({"sender": "ai",
                                                   "text": chunk.content,
                                                   "type": "stream",
                                                   "from_agent": current_node})
                    elif current_node == "quiz_generation":
                        if last_node != current_node:
                            print("\n--- Quiz Generation Node ---\n")
                            last_node = current_node
                        # print(chunk.content, end="", flush=True)
                        generated_quiz += chunk.content

                    elif current_node == "fallback_node":
                        if last_node != current_node:
                            print("\n--- Fallback Node ---\n")
                            last_node = current_node
                        # print(chunk.content, end="", flush=True)
                        await websocket.send_json({"sender": "ai",
                                                   "text": chunk.content,
                                                   "type": "stream",
                                                   "from_agent": current_node})

            
                    
            if generated_quiz:
                print(f"\nGenerated Quiz: {generated_quiz}\n")
                # extracted_quiz = extract_mcq(generated_quiz)
                extracted_quiz = save_quiz(extract_mcq(generated_quiz), user_id)
                print(f"\nExtracted Quiz: {extracted_quiz}\n")
                extracted_quiz["created_at"] = extracted_quiz["created_at"].isoformat()
                # print(f"\nQuiz question generated: {extracted_quiz}\n")
                # to write function here to save the quiz in firestore
                await websocket.send_json({"sender": "ai",
                                           "text": extracted_quiz,
                                           "from_agent": "quiz_generator"})
                
        except Exception as e:
            print(f"Websocket error: {e}")
            break



