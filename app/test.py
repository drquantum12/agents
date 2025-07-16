from utility.custom_libs import CustomMongoDBChatMessageHistory
from langgraph.graph import StateGraph, START, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from pymongo import MongoClient
from langchain_core.runnables import RunnableConfig
import os
from typing import TypedDict
from llm import LLM

llm = LLM().get_llm()

class AgentState(TypedDict):
    messages: list[BaseMessage]

def get_chat_history(session_id: str):
    return CustomMongoDBChatMessageHistory(
        session_id=session_id,
        connection_string=os.getenv("MONGODB_CONNECTION_STRING"),
        database_name="neurosattva",
        collection_name="sessions",
        max_recent_messages=100
    )


chat_history = get_chat_history("test_session")

def call_model(state: AgentState, config: RunnableConfig):
    if "configurable" not in config or "session_id" not in config["configurable"]:
        raise ValueError("Session ID is required in the configuration.")
    
    chat_history = get_chat_history(config["configurable"]["session_id"])
    messages = list(chat_history.messages) + state.get("messages", [])
    ai_message = llm.invoke(messages)
    chat_history.add_ai_message(ai_message.content)
    state["messages"] = messages + [ai_message]
    return {"messages": ai_message}


builder = StateGraph(AgentState)
builder.add_edge(START, "model")
builder.add_node("model", call_model)

graph = builder.compile()



if __name__ == "__main__":
    config = {"configurable": {"session_id": "test_session"}}
    
    input_message = HumanMessage(content="What does the word 'neurosattva' mean?")
    chat_history.add_user_message(input_message.content)

    for chunk, metadata in graph.stream({"messages": [input_message]}, config=config, stream_mode="messages"):
        token = chunk.content if hasattr(chunk, 'content') else str(chunk)
        print(token, end='', flush=True)

    # for chunk in agent.stream(state,
    #                                     config={"configurable":{"session_id": "test_session"}}):
    #     token = chunk.content if hasattr(chunk, 'content') else str(chunk)
    #     print(token, end='', flush=True)




    # Example usage
    # chat_history.add_user_message("Hello, how are you?")
    # chat_history.add_ai_message("I'm doing well, thank you!")
    # chat_history.add_user_message("Hi, My name is Arjun Singh Tomar and I am 27 years old.")
    
    # Retrieve all messages
    # messages = chat_history.messages
    # print(messages)
    # msgs = chat_history.find({"SessionId": "test_session"})
    # for msg in msgs:    
    #     print(msg.todict())
    
    # Clear the chat history
    # chat_history.clear()