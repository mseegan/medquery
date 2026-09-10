from typing import Literal

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    role: Literal["patient", "doctor"]
    user_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    agent_trace: list[str] = []
    disclaimer: str | None = None
