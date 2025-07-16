from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from pymongo import MongoClient
from google.cloud import firestore
from datetime import datetime

class CustomMongoDBChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, session_id: str, connection_string: str, database_name: str, collection_name: str, max_recent_messages: int = 100):
        self.session_id = session_id
        self.client = MongoClient(connection_string)
        self.collection = self.client[database_name][collection_name]
        self.max_recent_messages = max_recent_messages

        # Initialize if doesn't exist
        existing = self.collection.find_one({"_id": session_id})
        if not existing:
            self.collection.insert_one({"_id": session_id, "messages": []})

    @property
    def messages(self) -> list[BaseMessage]:
        doc = self.collection.find_one({"_id": self.session_id}, {"messages": {"$slice": -self.max_recent_messages}})
        messages = doc.get("messages", [])
        
        # Optional: sort messages by timestamp
        messages.sort(key=lambda x: x.get("timestamp", ""))
        
        return [self._dict_to_message(msg) for msg in messages]

    def add_user_message(self, message: str) -> None:
        self._append_message(HumanMessage(content=message))

    def add_ai_message(self, message: str) -> None:
        self._append_message(AIMessage(content=message))

    def _append_message(self, message: BaseMessage) -> None:
        self.collection.update_one(
            {"_id": self.session_id},
            {"$push": {"messages": self._message_to_dict(message)}}
        )

    def clear(self) -> None:
        self.collection.update_one({"_id": self.session_id}, {"$set": {"messages": []}})

    def _message_to_dict(self, message: BaseMessage) -> dict:
        return {
            "type": message.type,
            "data": {
                "content": message.content
            },
            "timestamp": datetime.now()
        }

    def _dict_to_message(self, data: dict) -> BaseMessage:
        msg_type = data["type"]
        content = data["data"]["content"]
        if msg_type == "human":
            return HumanMessage(content=content)
        elif msg_type == "ai":
            return AIMessage(content=content)
        else:
            raise ValueError(f"Unsupported message type: {msg_type}")
        

class FirestoreChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, session_id: str, collection_name: str = "chat_histories"):
        self.session_id = session_id
        self.client = firestore.Client()
        self.collection = self.client.collection(collection_name)
        self.document = self.collection.document(session_id)

        # Initialize document if it doesn't exist
        if not self.document.get().exists:
            self.document.set({"messages": []})

    @property
    def messages(self) -> list[BaseMessage]:
        doc = self.document.get()
        if not doc.exists:
            return []
        messages_data = doc.to_dict().get("messages", [])
        return [self._dict_to_message(msg) for msg in messages_data]

    def add_user_message(self, message: str) -> None:
        self._append_message(HumanMessage(content=message))

    def add_ai_message(self, message: str) -> None:
        self._append_message(AIMessage(content=message))

    def _append_message(self, message: BaseMessage) -> None:
        self.document.update({
            "messages": firestore.ArrayUnion([self._message_to_dict(message)])
        })

    def clear(self) -> None:
        self.document.set({"messages": []})

    def _message_to_dict(self, message: BaseMessage) -> dict:
        return {
            "type": message.type,
            "data": {
                "content": message.content
            }
        }

    def _dict_to_message(self, data: dict) -> BaseMessage:
        msg_type = data["type"]
        content = data["data"]["content"]
        if msg_type == "human":
            return HumanMessage(content=content)
        elif msg_type == "ai":
            return AIMessage(content=content)
        else:
            raise ValueError(f"Unsupported message type: {msg_type}")