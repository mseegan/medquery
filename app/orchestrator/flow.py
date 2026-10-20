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


# What each graph step is doing, in words for a progress display.
STEP_LABELS = {
    "understand_request": "Understanding the request",
    "make_plan": "Planning the steps",
    "run_history": "Checking the patient's history",
    "run_research": "Researching the condition",
    "run_booking": "Working on the booking",
    "compose_reply": "Writing the reply",
}


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _turn_result(final_message) -> TurnResult:
    return TurnResult(
        reply=final_message.content,
        agents=final_message.additional_kwargs.get("agents", []),
        used_reference=final_message.additional_kwargs.get("used_reference", False),
    )


def chat_turn(thread_id: str, message: str) -> TurnResult:
    """Run one user message through the flow and return the reply."""
    result = flow.invoke(
        {"messages": [{"role": "user", "content": message}]}, config=_config(thread_id)
    )
    return _turn_result(result["messages"][-1])


def stream_turn(thread_id: str, message: str):
    """Like chat_turn, but yields ("start", label) as each step begins and
    ("done", label) as it finishes, then ("reply", TurnResult) at the end."""
    config = _config(thread_id)
    for event in flow.stream(
        {"messages": [{"role": "user", "content": message}]}, config, stream_mode="tasks"
    ):
        label = STEP_LABELS.get(event["name"])
        if not label:
            continue
        if "result" not in event:
            yield "start", label
        elif not event.get("error"):
            yield "done", label
    yield "reply", _turn_result(flow.get_state(config).values["messages"][-1])
