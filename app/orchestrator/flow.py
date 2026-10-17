from dataclasses import dataclass

from langgraph.graph import END, START, StateGraph

from app.agents.stages import build_booking_agent, build_history_agent
from app.db.checkpoints import make_checkpointer
from app.orchestrator.nodes import (
    advance_plan,
    compose_reply,
    make_plan,
    run_research,
    understand_request,
)
from app.orchestrator.state import FlowState, current_step

# Plan step agent -> graph node that runs it.
STEP_NODES = {"history": "run_history", "research": "run_research", "booking": "run_booking"}


def _node_for_current_step(state) -> str | None:
    step = current_step(state)
    return STEP_NODES[step["agent"]] if step else None


def _entry(state) -> str:
    """A plan that is still waiting on the patient continues; otherwise the
    message starts a new request."""
    return _node_for_current_step(state) or "understand_request"


def _after_plan(state) -> str:
    return _node_for_current_step(state) or "compose_reply"


def _after_step(state) -> str:
    """Continue into the next step if this one finished; otherwise the patient
    needs to reply, so answer now."""
    if state.get("step_finished"):
        return _node_for_current_step(state) or "compose_reply"
    return "compose_reply"


def build_flow():
    builder = StateGraph(FlowState)
    builder.add_node("understand_request", understand_request)
    builder.add_node("make_plan", make_plan)
    builder.add_node("run_history", build_history_agent())
    builder.add_node("run_research", run_research)
    builder.add_node("run_booking", build_booking_agent())
    builder.add_node("advance_plan", advance_plan)
    builder.add_node("compose_reply", compose_reply)

    builder.add_conditional_edges(START, _entry)
    builder.add_edge("understand_request", "make_plan")
    builder.add_conditional_edges("make_plan", _after_plan)
    for node in STEP_NODES.values():
        builder.add_edge(node, "advance_plan")
    builder.add_conditional_edges("advance_plan", _after_step)
    builder.add_edge("compose_reply", END)

    return builder.compile(checkpointer=make_checkpointer())


flow = build_flow()


@dataclass
class TurnResult:
    reply: str
    agents: list[str]
    used_reference: bool


def chat_turn(thread_id: str, message: str) -> TurnResult:
    """Run one user message through the flow and return the reply."""
    result = flow.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    final = result["messages"][-1]
    return TurnResult(
        reply=final.content,
        agents=final.additional_kwargs.get("agents", []),
        used_reference=final.additional_kwargs.get("used_reference", False),
    )
