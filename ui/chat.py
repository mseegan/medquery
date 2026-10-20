"""Conversation helpers: the chat id kept in the URL, and what the saved
conversation holds."""
import uuid

import streamlit as st

from app.orchestrator.flow import flow


def current_chat_id() -> str:
    """The conversation id lives in the URL, so a refresh resumes the same chat."""
    chat_id = st.query_params.get("chat")
    if not chat_id:
        chat_id = uuid.uuid4().hex
        st.query_params["chat"] = chat_id
    return chat_id


def start_new_chat() -> None:
    st.query_params["chat"] = uuid.uuid4().hex


def conversation_state(chat_id: str) -> dict:
    return flow.get_state({"configurable": {"thread_id": chat_id}}).values or {}


def transcript(chat_id: str) -> list[dict]:
    """The saved conversation as display messages: role, text, used_reference."""
    shown = []
    for message in conversation_state(chat_id).get("messages", []):
        if message.type == "human":
            shown.append({"role": "user", "text": message.content, "used_reference": False})
        elif message.type == "ai" and not message.tool_calls and isinstance(message.content, str):
            if message.content.strip():
                shown.append(
                    {
                        "role": "assistant",
                        "text": message.content,
                        "used_reference": message.additional_kwargs.get("used_reference", False),
                    }
                )
    return shown
