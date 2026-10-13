from fastapi import APIRouter, HTTPException

from app.agents.prompts import DISCLAIMER
from app.orchestrator.flow import chat_turn
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        turn = chat_turn(request.session_id, request.message)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent run failed: {exc}") from exc

    return ChatResponse(
        reply=turn.reply,
        agent_trace=turn.agents,
        disclaimer=DISCLAIMER if turn.used_reference else None,
    )
