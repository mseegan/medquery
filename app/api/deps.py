KNOWN_AGENTS = {"appointment_agent", "reference_agent"}


def extract_agent_trace(messages) -> list[str]:
    """Best-effort list of which sub-agents contributed to a supervisor run,
    derived from the `name` tag LangGraph attaches to sub-agent messages."""
    trace = []
    for message in messages:
        name = getattr(message, "name", None)
        if name in KNOWN_AGENTS and name not in trace:
            trace.append(name)
    return trace


def require_doctor_role(role: str, agent_trace: list[str]) -> None:
    """Defense-in-depth check: reference_agent should never appear in a
    patient-role trace, since it isn't wired into the patient supervisor
    graph at all. Raises if that invariant is somehow violated."""
    if role != "doctor" and "reference_agent" in agent_trace:
        raise PermissionError("reference_agent is doctor-only.")
