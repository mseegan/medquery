from langchain_core.tools import tool

from app.db import scheduling
from app.db.availability import next_openings
from app.tools.common import ToolCallId, commit


@tool
def find_doctors(specialty: str) -> str:
    """List the doctors in a specialty with their next open appointment times."""
    with scheduling.get_session() as session:
        doctors = (
            session.query(scheduling.Doctor)
            .filter(scheduling.Doctor.specialty.ilike(specialty.strip()))
            .all()
        )
        if not doctors:
            return f"No doctors found for specialty '{specialty}'."

        lines = []
        for doctor in doctors:
            openings = ", ".join(
                f"{slot:%a %Y-%m-%d %H:%M}" for slot in next_openings(session, doctor.doctor_id)
            )
            lines.append(
                f"{doctor.doctor_id} | {doctor.name} | {doctor.specialty} | "
                f"next openings: {openings or 'none'}"
            )
        return "\n".join(lines)


@tool
def select_doctor(doctor_id: str, tool_call_id: ToolCallId):
    """Record the doctor the patient chose to see."""
    with scheduling.get_session() as session:
        doctor = session.get(scheduling.Doctor, doctor_id)
        if doctor is None:
            return f"Error: no doctor with id '{doctor_id}'."
        return commit(
            tool_call_id,
            f"Selected {doctor.name} ({doctor.specialty}).",
            doctor_id=doctor.doctor_id,
            doctor_name=doctor.name,
            proposed_slot=None,
        )
