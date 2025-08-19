from fastapi import APIRouter, HTTPException, Header, Depends, status, Query
from datetime import datetime
from pydantic import BaseModel
from utility.auth import get_current_user_from_firebase_token
from uuid import uuid4
from db_utility.mongo_db import mongo_db
from core_agents import build_agent, AgentState, generate_topic, get_image_urls
from langchain_core.messages import AIMessageChunk
from utility.preprocessing import extract_mcq
from fastapi import WebSocket
from utility.quizzes import save_quiz
from db_utility.vector_db import VectorDB
from utility.custom_libs import CustomMongoDBChatMessageHistory
import os, json

vector_db = VectorDB()

class MessageSchema(BaseModel):
    content: str

mongodb_user_collection = mongo_db["users"]
mongodb_session_collection = mongo_db["sessions"]
mongodb_quiz_collection = mongo_db["quizzes"]
mongodb_conversations_collection = mongo_db["conversations"]

chat_router = APIRouter(
    responses={404: {"description": "Not found"}},
)

def get_chat_history(session_id: str):
    return CustomMongoDBChatMessageHistory(
        session_id=session_id,
        connection_string=os.getenv("MONGODB_CONNECTION_STRING"),
        database_name="neurosattva",
        collection_name="sessions",
        max_recent_messages=100
    )

@chat_router.post("/")
def chat(message: MessageSchema, current_user: dict = Depends(get_current_user_from_firebase_token)):

    try:
        # adding new coversation id to the list of conversation ids for the user

        new_conversation_id = str(uuid4())
        conversation_topic = generate_topic(message.content)
        

    

        mongodb_conversations_collection.insert_one({
            "_id": new_conversation_id,
            "user_id": current_user["uid"],
            "topic": conversation_topic,
            "created_at": datetime.now()
        })

        return {"message": "New conversation created", "conversation_id": new_conversation_id, "topic": conversation_topic}

        
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating conversation: {str(e)}",
        )
    
@chat_router.get("/conversations")
def get_conversations(limit: int = Query(10, ge=1),
                    offset: int = Query(0, ge=0),
                       current_user: dict = Depends(get_current_user_from_firebase_token)):
    """
    Get all conversations for the current user.
    """
    try:
        query = {"user_id": current_user["uid"]}
        total = mongodb_conversations_collection.count_documents(query)

        cursor = mongodb_conversations_collection.find(query, {"_id": 1, "topic": 1, "created_at": 1}).sort("created_at", -1).skip(offset).limit(limit)
        conversations = [
            {
                "id": str(doc["_id"]),
                "topic": doc["topic"],
                "created_at": doc["created_at"].isoformat()
            }
            for doc in cursor
        ]
        return {"conversation_ids": conversations, "total": total}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving conversations: {str(e)}",
        )

# implementing lazy loading using limit and offset
@chat_router.get("/conversation/{conversation_id}")
def get_paginated_conversation(conversation_id: str, limit: int = 10, offset: int = 0, current_user: dict = Depends(get_current_user_from_firebase_token)
                                ):
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

    if result:

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
            "id": conversation_id,
            "messages": messages,
            "total_messages": total_messages
        }


@chat_router.websocket("/ws/ai-tutor")
async def websocket_endpoint(websocket: WebSocket):

    user_id = websocket.query_params.get("user_id")
    conversation_id = websocket.query_params.get("conversation_id")
    # conversation_id = user_get_or_create_conversation_id(user_id)

    if not user_id or not conversation_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid user_id or conversation_id")
        return
    
    await websocket.accept()

    agent = build_agent()
    config = {"configurable": {"session_id": conversation_id}}

    while True:
        try:
            data = await websocket.receive_json()
            usr_msg = data.get("payload")
            personalized_response = data.get("personalized_response", False)
            source_list = None

            print(f"Received message: {usr_msg}, personalized_response: {personalized_response}")

            if personalized_response:
                context, source_list = vector_db.get_similar_documents(usr_msg, top_k=3)
                print(f"Context: {context}, Source List: {source_list}")

            state = AgentState(
                question=usr_msg,
                context=context if personalized_response else "",
                grade=data.get("grade", ""),
                board=data.get("board", ""),
                personalized_response=personalized_response,
                full_explanation="",
                messages=[],
                stage="start",
                intent=""
            )

            generated_quiz = ""
            full_explanation = ""
            last_node = None

            if personalized_response and source_list:
                await websocket.send_json({"sender": "ai",
                                           "text": source_list,
                                           "from_agent": "response_source"})

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
                        full_explanation += chunk.content
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

            
            if full_explanation:
                images = get_image_urls(full_explanation)
                chat_history = get_chat_history(config["configurable"]["session_id"])
                chat_history.add_user_message(state.get("question"))

                if personalized_response and source_list:
                    chat_history.add_ai_message(full_explanation, sources=source_list, image_links=images)
                else:
                    chat_history.add_ai_message(full_explanation, image_links=images)
                res = {"sender": "ai",
                                           "text": images,
                                           "from_agent": "media_generator"}
                print(f"Image URLs: {res}")
                await websocket.send_json({"sender": "ai",
                                           "text": images,
                                           "from_agent": "media_generator"})
                
            if generated_quiz:
                print(f"\nGenerated Quiz: {generated_quiz}\n")
                # extracted_quiz = extract_mcq(generated_quiz)
                extracted_quiz = save_quiz(extract_mcq(generated_quiz))
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


# a test function to simulate model response
@chat_router.websocket("/ws/ai-tutor/test")
async def websocket_test_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        try:
            data = await websocket.receive_json()
            usr_msg = data.get("payload")
            personalized_response = data.get("personalized_response", False)
            if personalized_response:
                with open("app/assets/sample_ai_response_personalized.json", "r") as f:
                    sample_response = json.load(f)
            else:
            # reading sample saved model response from a file
                with open("app/assets/sample_ai_response.json", "r") as f:
                    sample_response = json.load(f)
            
            # iterating over the sample response and sending it as a stream
            for chunk in sample_response:
                await websocket.send_json({"sender": "ai",
                                           "text": chunk["text"],
                                           "type": chunk.get("type", "stream"),
                                           "from_agent": chunk["from_agent"]})
        except Exception as e:
            print(f"Websocket error: {e}")
            break

