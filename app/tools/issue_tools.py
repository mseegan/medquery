from langchain_core.tools import tool

from app.db import scheduling
from app.tools.common import ToolCallId, commit


def list_specialties() -> list[str]:
    with scheduling.get_session() as session:
        rows = session.query(scheduling.Doctor.specialty).distinct().all()
    return sorted(r[0] for r in rows)


@tool
def recommend_specialty(specialty: str, issue_summary: str, tool_call_id: ToolCallId):
    """Record the specialty that best fits the patient's concern, along with a
    one-sentence summary of the concern. The specialty must be one the clinic
    offers."""
    valid = {s.lower(): s for s in list_specialties()}
    canonical = valid.get(specialty.strip().lower())
    if canonical is None:
        return f"Error: '{specialty}' isn't offered. Choose one of: {', '.join(valid.values())}."
    return commit(
        tool_call_id,
        f"Recorded specialty {canonical}.",
        specialty=canonical,
        issue_summary=issue_summary.strip(),
    )
