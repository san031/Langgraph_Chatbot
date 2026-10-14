import streamlit as st
from langgraph_database_backend import chatbot, retrieve_all_threads, get_titles,save_title

from langchain_core.messages import HumanMessage,AIMessage

import uuid


def generate_thread_id():
    return str(uuid.uuid4())


def add_thread(thread_id):
    if thread_id not in st.session_state["chat_threads"]:
        st.session_state["chat_threads"].append(thread_id)


def reset_chat():
    thread_id = generate_thread_id()
    st.session_state["thread_id"] = thread_id
    add_thread(thread_id)
    st.session_state["message_history"] = []  # reset message history for the new thread


def load_conversation(thread_id):
    state = chatbot.get_state(config={"configurable": {"thread_id": thread_id}})
    return state.values.get("messages", [])


## session set up

if "message_history" not in st.session_state:
    st.session_state["message_history"] = []

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = generate_thread_id()

if "chat_threads" not in st.session_state:
    st.session_state["chat_threads"] = retrieve_all_threads()

if "thread_titles" not in st.session_state:
    st.session_state["thread_titles"] = {}   # thread_id -> first word typed by the user

add_thread(st.session_state["thread_id"])

titles = get_titles()


### sidebar ###

st.sidebar.title("langgraph chatbot with db")

if st.sidebar.button("new Chat"):
    reset_chat()

st.sidebar.header("My conversations")

for thread_id in st.session_state["chat_threads"][::-1]:

    if thread_id in titles:
        label = titles[thread_id]
    elif thread_id == st.session_state["thread_id"]:
        label = "New chat"
    else:
        label = str(thread_id)[:8] 
    # label = st.session_state["thread_titles"].get(thread_id, "New chat")
    
    
    if st.sidebar.button(label,str(thread_id)):
        st.session_state["thread_id"] = thread_id
        messages = load_conversation(thread_id)

        temp_messages = []
        for msg in messages:
            role = "user" if isinstance(msg, HumanMessage) else "assistant"
            temp_messages.append({"role": role, "content": msg.content})
        st.session_state["message_history"] = temp_messages


## main ui ###

for message in st.session_state["message_history"]:
    with st.chat_message(message['role']):
        st.text(message["content"])

user_input = st.chat_input("type your message here...")

if user_input:
    thread_id = st.session_state["thread_id"]
    
        # save the first word of the first message as this thread's sidebar title
    is_first_message = thread_id not in titles
    if is_first_message:
        save_title(thread_id, user_input.split()[0])
    st.session_state["message_history"].append({"role":"user", "content":user_input})

    with st.chat_message("user"):
        st.text(user_input)

    CONFIG = {
        "configurable":{
            "thread_id":st.session_state["thread_id"]
        },
        "metadata": {
            "thread_id":st.session_state["thread_id"]
        },
        "run_name" : "chat_turn",
    }


    with st.chat_message("assistant"):
            def ai_only_stream():
                for message_chunk, metadata in chatbot.stream(
                    {"messages": [HumanMessage(content=user_input)]},
                    config=CONFIG,
                    stream_mode="messages",
                ):
                    if isinstance(message_chunk, AIMessage):
                        content = message_chunk.content
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    yield block.get("text", "")
                        else:
                            yield content

            ai_message = st.write_stream(ai_only_stream())

    st.session_state["message_history"].append({"role":"assistant", "content":ai_message})

    if is_first_message:
            st.rerun()