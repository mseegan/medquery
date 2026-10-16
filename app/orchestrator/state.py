from langgraph.prebuilt.chat_agent_executor import AgentState


class FlowState(AgentState):
    """Conversation state shared by the planner and the agents. Tools fill in
    the patient, doctor, and booking fields; the planner owns request and plan."""

    patient_id: str | None
    patient_name: str | None
    patient_relationship: str | None
    issue_summary: str | None
    specialty: str | None
    doctor_id: str | None
    doctor_name: str | None
    proposed_slot: str | None
    appointment_id: str | None
    request: dict | None  # the structured RequestSummary for the current request
    plan: list[dict] | None  # ordered steps: agent, goal, status, optional args
    step_finished: bool | None


def current_step(state) -> dict | None:
    """The first plan step that isn't done, or None when there is no active plan."""
    for step in state.get("plan") or []:
        if step["status"] != "done":
            return step
    return None
