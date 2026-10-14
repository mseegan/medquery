from datetime import datetime

from langchain_core.tools import tool
from sqlalchemy.exc import IntegrityError

from app.db import scheduling
from app.db.availability import is_open, open_slots
from app.tools.common import (
    NO_DOCTOR,
    NOT_IDENTIFIED,
    DoctorIdFromState,
    PatientIdFromState,
    ProposedSlotFromState,
    ToolCallId,
    commit,
)

MAX_SLOTS_SHOWN = 60


def _parse_slot(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.strip().replace(" ", "T"))
    except ValueError:
        return None


@tool
def get_availability(
    start_date: str, end_date: str, doctor_id: DoctorIdFromState = None
) -> str:
    """Get the selected doctor's open appointment times between two dates.

    Args:
        start_date: ISO date, e.g. "2026-10-19".
        end_date: ISO date, e.g. "2026-10-23".
    """
    if not doctor_id:
        return NO_DOCTOR
    try:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)
    except ValueError:
        return "Error: start_date and end_date must be ISO dates like '2026-10-19'."

    with scheduling.get_session() as session:
        doctor = session.get(scheduling.Doctor, doctor_id)
        slots = open_slots(session, doctor_id, start, end)

    if not slots:
        return f"No open times for {doctor.name} between {start_date} and {end_date}."
    shown = slots[:MAX_SLOTS_SHOWN]
    lines = [f"{s:%a %Y-%m-%d %H:%M}" for s in shown]
    if len(slots) > len(shown):
        lines.append(f"...and {len(slots) - len(shown)} more later in the range.")
    return f"Open times for {doctor.name}:\n" + "\n".join(lines)


@tool
def propose_booking(
    slot: str,
    tool_call_id: ToolCallId,
    patient_id: PatientIdFromState = None,
    doctor_id: DoctorIdFromState = None,
):
    """Hold an open time for the patient with their selected doctor, pending
    the patient's confirmation. slot is 'YYYY-MM-DD HH:MM'. Nothing is booked
    until confirm_booking is called."""
    if not patient_id:
        return NOT_IDENTIFIED
    if not doctor_id:
        return NO_DOCTOR

    when = _parse_slot(slot)
    if when is None:
        return "Error: slot must look like '2026-10-19 09:30'."

    with scheduling.get_session() as session:
        doctor = session.get(scheduling.Doctor, doctor_id)
        if not is_open(session, doctor_id, when):
            return f"Error: {when:%a %Y-%m-%d %H:%M} isn't an open time for {doctor.name}."

    return commit(
        tool_call_id,
        f"Held {when:%A %Y-%m-%d %H:%M} with {doctor.name}. Ask the patient to confirm; "
        "call confirm_booking only after they say yes.",
        proposed_slot=when.isoformat(),
    )


@tool
def confirm_booking(
    tool_call_id: ToolCallId,
    patient_id: PatientIdFromState = None,
    doctor_id: DoctorIdFromState = None,
    proposed_slot: ProposedSlotFromState = None,
):
    """Book the held time. Call this only after the patient has explicitly
    confirmed (e.g. 'yes, book it')."""
    if not patient_id:
        return NOT_IDENTIFIED
    if not doctor_id:
        return NO_DOCTOR
    if not proposed_slot:
        return "Error: no time is being held. Call propose_booking first."

    when = datetime.fromisoformat(proposed_slot)
    with scheduling.get_session() as session:
        doctor = session.get(scheduling.Doctor, doctor_id)
        if not is_open(session, doctor_id, when):
            return "Error: that time was just taken. Offer the patient another time."
        appointment = scheduling.Appointment(
            doctor_name=doctor.name,
            doctor_id=doctor.doctor_id,
            patient_id=patient_id,
            date=when,
        )
        session.add(appointment)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            return "Error: that time was just taken. Offer the patient another time."

        return commit(
            tool_call_id,
            f"Booked appointment {appointment.appointment_id}: {doctor.name} on "
            f"{when:%A %Y-%m-%d %H:%M}.",
            appointment_id=str(appointment.appointment_id),
            proposed_slot=None,
        )
