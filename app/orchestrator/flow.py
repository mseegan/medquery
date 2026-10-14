from dataclasses import dataclass

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.stages import (
    build_history_agent,
    build_issue_agent,
    build_routing_agent,
    build_scheduling_agent,
)
from app.orchestrator.state import STAGES, FlowState, next_stage

REFERENCE_TOOLS = {"medlineplus_search", "who_fact_sheet_search", "who_gho_lookup"}


def _reset_for_new_request(state) -> dict:
    """After a booking, the next message starts a fresh request for the same
    identified patient."""
    return {
        "issue_summary": None,
        "specialty": None,
        "doctor_id": None,
        "doctor_name": None,
        "proposed_slot": None,
        "appointment_id": None,
    }


def _entry(state) -> str:
    if state.get("appointment_id"):
        return "reset"
    return next_stage(state) or END


def _advance_when_done(field: str):
    """After a stage runs, continue straight into the next stage if this one
    finished; otherwise wait for the patient's reply."""

    def route(state) -> str:
        return (next_stage(state) or END) if state.get(field) else END

    return route


def build_flow():
    builder = StateGraph(FlowState)
    builder.add_node("history", build_history_agent())
    builder.add_node("issue", build_issue_agent())
    builder.add_node("routing", build_routing_agent())
    builder.add_node("scheduling", build_scheduling_agent())
    builder.add_node("reset", _reset_for_new_request)

    builder.add_conditional_edges(START, _entry)
    builder.add_edge("reset", "issue")
    for stage, field in STAGES:
        builder.add_conditional_edges(stage, _advance_when_done(field))

    return builder.compile(checkpointer=MemorySaver())


flow = build_flow()


@dataclass
class TurnResult:
    reply: str
    agents: list[str]
    used_reference: bool


def _text(content) -> str:
    if isinstance(content, str):
        return content.strip()
    return "\n".join(
        block.get("text", "") for block in content if isinstance(block, dict)
    ).strip()


def chat_turn(thread_id: str, message: str) -> TurnResult:
    """Run one user message through the flow. The reply joins every stage that
    spoke this turn; used_reference marks turns that quoted MedlinePlus or WHO."""
    result = flow.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    messages = result["messages"]
    last_user = max(i for i, m in enumerate(messages) if m.type == "human")
    this_turn = messages[last_user + 1 :]
    ai_messages = [m for m in this_turn if m.type == "ai"]

    replies = [_text(m.content) for m in ai_messages if not m.tool_calls]
    return TurnResult(
        reply="\n\n".join(r for r in replies if r),
        agents=list(dict.fromkeys(m.name for m in ai_messages if m.name)),
        used_reference=any(m.type == "tool" and m.name in REFERENCE_TOOLS for m in this_turn),
    )
