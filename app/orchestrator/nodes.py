"""Graph nodes that turn a message into a plan, run the plan's non-agent steps,
track progress, and assemble the reply."""
from datetime import date

from langchain_core.messages import AIMessage, RemoveMessage

from app.chains.compose import compose
from app.chains.plan import plan_request
from app.chains.schemas import RequestSummary
from app.chains.understand import summarize_request
from app.db import scheduling
from app.memory.service import remember
from app.orchestrator.state import current_step, describe_audience
from app.tools.issue_tools import list_specialties
from app.tools.research_tools import research_disease

RESEARCH_AGENT_NAME = "research_tool"
ASSISTANT_NAME = "assistant"
SECTION_LABELS = {
    "history_agent": "history",
    RESEARCH_AGENT_NAME: "research",
    "booking_agent": "booking",
}
EMERGENCY_NOTE = (
    "If this is an emergency, call your local emergency number or go to the nearest "
    "emergency room now."
)


def _text(content) -> str:
    if isinstance(content, str):
        return content.strip()
    return "\n".join(
        block.get("text", "") for block in content if isinstance(block, dict)
    ).strip()


def _latest_user_message(messages) -> tuple[str, list]:
    """The newest human message's text, and the messages before it."""
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].type == "human":
            return _text(messages[index].content), list(messages[:index])
    return "", list(messages)


def understand_request(state) -> dict:
    """Summarize chain: structure what the patient just asked for."""
    message, earlier = _latest_user_message(state["messages"])
    request = summarize_request(
        message,
        prior_messages=earlier,
        patient_id=state.get("patient_id"),
        patient_name=state.get("patient_name"),
    )
    return {"request": request.model_dump()}


def make_plan(state) -> dict:
    """Plan chain: order the steps for this request and start it fresh. A request
    about a different person than the one identified (say, the patient's father)
    clears the identified patient so the history step finds the right record."""
    request = RequestSummary.model_validate(state["request"])
    relationship = request.patient.relationship.strip().lower() or "self"

    same_patient = bool(state.get("patient_id")) and relationship == (
        state.get("patient_relationship") or "self"
    )
    steps = plan_request(request, identified=same_patient)

    canonical = {s.lower(): s for s in list_specialties()}
    update = {
        "plan": steps,
        "patient_relationship": relationship,
        "issue_summary": ", ".join(request.conditions_mentioned + request.symptoms) or request.summary,
        "specialty": canonical.get((request.specialty or "").strip().lower()),
        "doctor_id": None,
        "doctor_name": None,
        "proposed_slot": None,
        "appointment_id": None,
        "step_finished": None,
        "new_request": True,
    }
    if not same_patient:
        update.update({"patient_id": None, "patient_name": None})
    return update


def run_research(state) -> dict:
    """Act: call the disease-research tool with the arguments the plan chose."""
    step = current_step(state)
    summary = research_disease.invoke(step["args"])
    return {"messages": [AIMessage(content=summary, name=RESEARCH_AGENT_NAME)]}


def _is_complete(step: dict, state) -> bool:
    if step["agent"] == "history":
        return bool(state.get("patient_id"))
    if step["agent"] == "booking":
        return bool(state.get("appointment_id"))
    return True  # research is one-shot


def _record_outcome(step: dict, state) -> None:
    """Save what a finished step established as long-term memory."""
    patient_id = state.get("patient_id")
    if not patient_id:
        return
    relationship = state.get("patient_relationship") or "self"

    if step["agent"] == "history" and relationship != "self":
        remember(
            patient_id,
            f"A family member acts on this patient's behalf (the patient is the requester's {relationship}).",
            source="planner",
            key="caregiver",
        )
    elif step["agent"] == "research":
        args = step["args"]
        remember(
            patient_id,
            f"On {date.today()}, asked about {args['focus']} of {args['disease']}.",
            source="planner",
            key=f"researched-{args['disease'].lower()}-{date.today()}",
        )
    elif step["agent"] == "booking":
        appointment_id = int(state["appointment_id"])
        with scheduling.get_session() as session:
            appointment = session.get(scheduling.Appointment, appointment_id)
        remember(
            patient_id,
            f"Booked an appointment with {appointment.doctor_name} on "
            f"{appointment.date:%Y-%m-%d %H:%M} for {state.get('issue_summary') or 'a visit'}.",
            source="planner",
            key=f"booked-{appointment_id}",
        )


def advance_plan(state) -> dict:
    """Mark the step that just ran as done if it finished. Otherwise it is
    waiting on the patient's reply, and the plan stays where it is."""
    steps = [dict(s) for s in state["plan"]]
    step = next(s for s in steps if s["status"] != "done")

    finished = _is_complete(step, state)
    if finished:
        step["status"] = "done"
        _record_outcome(step, state)
    return {"plan": steps, "step_finished": finished}


def compose_reply(state) -> dict:
    """Replace this turn's agent messages with one reply for the patient."""
    messages = state["messages"]
    last_user = max(i for i, m in enumerate(messages) if m.type == "human")
    parts = [
        m
        for m in messages[last_user + 1 :]
        if m.type == "ai" and not m.tool_calls and _text(m.content)
    ]

    sections = [(SECTION_LABELS.get(m.name, m.name or "agent"), _text(m.content)) for m in parts]
    if len(sections) > 1:
        audience = describe_audience(state.get("patient_relationship"))
        reply = compose(_text(messages[last_user].content), sections, audience)
    elif sections:
        reply = sections[0][1]
    else:
        reply = (
            "How can I help? I can look up or update a patient's history, research a "
            "condition, or book an appointment."
        )

    urgency = (state.get("request") or {}).get("urgency")
    if state.get("new_request") and urgency == "emergency":
        reply = f"{EMERGENCY_NOTE}\n\n{reply}"

    final = AIMessage(
        content=reply,
        name=ASSISTANT_NAME,
        additional_kwargs={
            "agents": list(dict.fromkeys(m.name for m in parts if m.name)),
            "used_reference": any(m.name == RESEARCH_AGENT_NAME for m in parts),
        },
    )
    return {
        "messages": [RemoveMessage(id=m.id) for m in parts] + [final],
        "new_request": False,
    }
