import sqlite3
from langchain_groq import ChatGroq
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
# from langgraph.checkpoint.sqlite import SqliteSaver
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
import os
# os.getenv()

load_dotenv()

llm = ChatGroq(model = "openai/gpt-oss-120b", temperature = 1.5)

class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def chat_node(state: ChatState):
    messages = state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

# conn = sqlite3.connect(
#     database='chatbot.db',
#     check_same_thread=False
# )

pool = ConnectionPool(
    conninfo=os.environ["SUPABASE_DB_URL"],
    max_size=5,
    kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
)

checkpointer = PostgresSaver(pool)
checkpointer.setup()

with pool.connection() as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_titles (
            thread_id TEXT PRIMARY KEY,
            title TEXT NOT NULL
        )
    """)


def save_title(thread_id, title):
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO chat_titles (thread_id, title) VALUES (%s, %s) "
            "ON CONFLICT (thread_id) DO NOTHING",
            (str(thread_id), title),
        )
 
 
def get_titles():
    with pool.connection() as conn:
        rows = conn.execute("SELECT thread_id, title FROM chat_titles").fetchall()
    return {r["thread_id"]: r["title"] for r in rows}


graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_edge(START, "chat_node")
graph.add_edge("chat_node", END)

chatbot = graph.compile(checkpointer=checkpointer)

def retrieve_all_threads():
    all_threads = set()
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config["configurable"]["thread_id"])
    return list(all_threads)