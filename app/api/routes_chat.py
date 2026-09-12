from fastapi import APIRouter, HTTPException

from app.agents.reference_agent import DISCLAIMER
from app.api.deps import extract_agent_trace
from app.orchestrator.supervisor import supervisor
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    config = {"configurable": {"thread_id": request.session_id}}

    try:
        result = supervisor.invoke(
            {"messages": [{"role": "user", "content": request.message}]},
            config=config,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent run failed: {exc}") from exc

    messages = result["messages"]
    agent_trace = extract_agent_trace(messages)

    reply = messages[-1].content
    if isinstance(reply, list):
        reply = "\n".join(block.get("text", "") for block in reply if isinstance(block, dict))

    disclaimer = DISCLAIMER if "reference_agent" in agent_trace else None
    return ChatResponse(reply=reply, agent_trace=agent_trace, disclaimer=disclaimer)
