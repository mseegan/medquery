from langgraph.prebuilt.chat_agent_executor import AgentState


class FlowState(AgentState):
    """Conversation state shared by every stage. Each field is filled in by a
    tool in the stage that owns it."""

    patient_id: str | None
    patient_name: str | None
    issue_summary: str | None
    specialty: str | None
    doctor_id: str | None
    doctor_name: str | None
    proposed_slot: str | None
    appointment_id: str | None


# Stage name -> the state field that marks it complete, in flow order.
STAGES: list[tuple[str, str]] = [
    ("history", "patient_id"),
    ("issue", "specialty"),
    ("routing", "doctor_id"),
    ("scheduling", "appointment_id"),
]


def next_stage(state) -> str | None:
    """The first stage whose output field is still empty, or None when the
    flow is complete."""
    for stage, field in STAGES:
        if not state.get(field):
            return stage
    return None
