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
