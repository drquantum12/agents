from langgraph.graph import StateGraph, START, END
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing import TypedDict
from prompts import AI_TUTOR_PROMPT, QUIZ_GENERATOR_PROMPT, SUMMARIZE_HISTORY_PROMPT, AI_TUTOR_PROMPT_PERSONALIZED, INTENT_EXTRACTOR_PROMPT, TOPIC_GENERATOR_PROMPT, GENERAL_FALLBACK_PROMPT, SEARCH_QUERY_GENERATION_PROMPT
from llm import LLM
import os
from utility.custom_libs import CustomMongoDBChatMessageHistory
from langchain_core.runnables import RunnableConfig
from utility.web_search import get_unique_image_urls

llm = LLM().get_llm()


class AgentState(TypedDict, total=False):
    question: str
    context: str
    grade: str
    board: str
    personalized_response: bool
    full_explanation: str
    messages: list[BaseMessage]
    stage: str
    intent: str

def get_image_urls(content: str):
    search_query = SEARCH_QUERY_GENERATION_PROMPT.invoke({"text": content})
    search_query_content = llm.invoke(search_query).content.strip()
    return get_unique_image_urls(search_query_content, num_results=10)

def get_chat_history(session_id: str):
    return CustomMongoDBChatMessageHistory(
        session_id=session_id,
        connection_string=os.getenv("MONGODB_CONNECTION_STRING"),
        database_name="neurosattva",
        collection_name="sessions",
        max_recent_messages=100
    )

def generate_topic(text: str):
    prompt = TOPIC_GENERATOR_PROMPT.invoke({"text": text})
    topic = llm.invoke(prompt).content.strip()
    return topic


def orchestrator_node(state: AgentState, config: RunnableConfig):
    print("--- Orchestrator Node ---")
    prompt = INTENT_EXTRACTOR_PROMPT.invoke({"text": state.get("question")})
    intent = llm.invoke(prompt).content.strip()
    state["intent"] = intent  # Store the intent in the state
    print(f"Extracted intent: {intent}")
    return state
    
def route_node(state: AgentState):
    intent = state.get("intent", "").lower()
    if "explanation" in intent:
        return "answering_node"
    elif "quiz" in intent:
        return "quiz_generation"
    elif "general" in intent or "meta" in intent:
        return "fallback_node"
    else:
        return "fallback_node"

def answering_node(state: AgentState, config: RunnableConfig):
    chat_history = get_chat_history(config["configurable"]["session_id"])
    state["messages"] = list(chat_history.messages) + state.get("messages", [])
    history_msgs = []
    
    for msg in state.get("messages", []):
        if isinstance(msg, HumanMessage):
            history_msgs.append(("human", msg.content))
        elif isinstance(msg, AIMessage):
            history_msgs.append(("assistant", msg.content))
    # passing only the last 10 messages to the AI tutor prompt
    # If personalized response is enabled, use the personalized prompt
    if state.get("personalized_response", False):
        question = AI_TUTOR_PROMPT_PERSONALIZED.invoke({
            "history": history_msgs[-10:],
            "query": state.get("question"),
            "grade": state.get("grade", "10"),
            "context": state.get("context", "")
        })
    else:
        question = AI_TUTOR_PROMPT.invoke({"history": history_msgs[-10:], "query": state.get("question")})

    content = llm.invoke(question).content.strip()
    # chat_history.add_user_message(state.get("question"))
    # chat_history.add_ai_message(content)
    state["full_explanation"] = content
    state["stage"] = "quiz_generation"
    return state

def quiz_generation_node(state: AgentState, config: RunnableConfig):
    if not state.get("full_explanation"):
        print("No full explanation found, summarizing history instead.")
        chat_history = get_chat_history(config["configurable"]["session_id"])
        
        state["messages"] = list(chat_history.messages) + state.get("messages", [])
        
        history_msgs = ""
        for msg in state.get("messages", [])[-10:]:
            if isinstance(msg, HumanMessage):
                history_msgs += f"User: {msg.content}\n"
            elif isinstance(msg, AIMessage):
                history_msgs += f"AI: {msg.content}\n"
        summarization_prompt = SUMMARIZE_HISTORY_PROMPT.invoke({"history": history_msgs})
        summarization = llm.invoke(summarization_prompt).content.strip()
        state["full_explanation"] = summarization

    quiz_prompt = QUIZ_GENERATOR_PROMPT.invoke({"text": state.get("full_explanation", "No explanation provided")})
    content = llm.invoke(quiz_prompt).content.strip()
    state["quiz_question"] = content
    # print(f"final state: {state}")
    return state

def fallback_node(state: AgentState, config: RunnableConfig):
    chat_history = get_chat_history(config["configurable"]["session_id"])
    state["messages"] = list(chat_history.messages) + state.get("messages", [])
    history_msgs = []
    for msg in state.get("messages", []):
        if isinstance(msg, HumanMessage):
            history_msgs.append(("human", msg.content))
        elif isinstance(msg, AIMessage):
            history_msgs.append(("assistant", msg.content))

    prompt = GENERAL_FALLBACK_PROMPT.invoke({"history": history_msgs[-10:], "question": state.get("question", "")})
    state["full_explanation"] = llm.invoke(prompt).content.strip()
    chat_history.add_user_message(state.get("question"))
    chat_history.add_ai_message(state.get("full_explanation"))
    state["stage"] = "completed"
    return state

def build_agent():
    agent_builder = StateGraph(AgentState)

    # Declare node names
    agent_builder.add_node("orchestrator", orchestrator_node)  # Orchestrator node
    agent_builder.add_node("answering_node", answering_node)
    agent_builder.add_node("quiz_generation", quiz_generation_node)
    agent_builder.add_node("fallback_node", fallback_node)

    # Conditional branching logic
    agent_builder.add_conditional_edges(
        "orchestrator", 
        route_node,
        {
            "answering_node": "answering_node",
            "quiz_generation": "quiz_generation",
            "fallback_node": "fallback_node"
        }
        )

    # Connections
    agent_builder.add_edge(START, "orchestrator")
    agent_builder.add_edge("answering_node", "quiz_generation")
    agent_builder.add_edge("quiz_generation", END)
    agent_builder.add_edge("fallback_node", END)

    agent_builder.set_entry_point("orchestrator")
    agent_builder.set_finish_point("quiz_generation")

    return agent_builder.compile()