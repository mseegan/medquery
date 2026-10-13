import uuid
from datetime import datetime
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from app.db.database import get_session
from app.db.models import Appointment, AppointmentSlot, Doctor, Patient, PendingBooking

# Injected from flow state, so the model never supplies (or can alter) these.
PatientIdFromState = Annotated[str | None, InjectedState("patient_id")]
DoctorIdFromState = Annotated[str | None, InjectedState("doctor_id")]
ToolCallId = Annotated[str, InjectedToolCallId]

NOT_IDENTIFIED = "Error: the patient hasn't been identified yet."


def _commit(tool_call_id: str, content: str, **state_updates) -> Command:
    """Tool result that also records values in the flow state."""
    return Command(
        update={
            **state_updates,
            "messages": [ToolMessage(content=content, tool_call_id=tool_call_id)],
        }
    )


def list_specialties() -> list[str]:
    with get_session() as session:
        rows = session.query(Doctor.specialty).distinct().all()
    return sorted(r[0] for r in rows)


@tool
def identify_patient(
    first_name: str,
    last_name: str,
    tool_call_id: ToolCallId,
    dob: str | None = None,
) -> str | Command:
    """Identify the patient from their first and last name, creating a new
    patient record if none exists. If several patients share the name, this
    asks for a date of birth (YYYY-MM-DD); call it again with dob set."""
    full_name = f"{first_name.strip()} {last_name.strip()}".strip()
    with get_session() as session:
        matches = session.query(Patient).filter(Patient.name.ilike(full_name)).all()
        if dob:
            matches = [p for p in matches if p.dob == dob.strip()]

        if len(matches) > 1:
            return (
                "Several patients share that name. Ask the user for their date of "
                "birth (YYYY-MM-DD) and call identify_patient again with dob set."
            )

        if len(matches) == 1:
            patient = matches[0]
            message = f"Found existing patient {patient.name}."
        else:
            patient = Patient(
                id=str(uuid.uuid4()),
                name=full_name,
                dob=dob.strip() if dob else "",
                mrn_fake=f"MRN-{uuid.uuid4().hex[:6].upper()}",
            )
            session.add(patient)
            session.flush()
            message = f"Created a new patient record for {patient.name}."

        return _commit(
            tool_call_id, message, patient_id=patient.id, patient_name=patient.name
        )


@tool
def get_patient_records(patient_id: PatientIdFromState = None) -> str:
    """Get the identified patient's upcoming appointments and past visits."""
    if not patient_id:
        return NOT_IDENTIFIED

    with get_session() as session:
        patient = session.get(Patient, patient_id)
        rows = (
            session.query(Appointment, AppointmentSlot, Doctor)
            .join(AppointmentSlot, Appointment.slot_id == AppointmentSlot.id)
            .join(Doctor, Appointment.doctor_id == Doctor.id)
            .filter(
                Appointment.patient_id == patient_id,
                Appointment.status.in_(["confirmed", "completed"]),
            )
            .order_by(AppointmentSlot.start_time)
            .all()
        )
        if not rows:
            return f"No previous records on file for {patient.name} (new patient)."

        now = datetime.now()
        upcoming = [r for r in rows if r[1].start_time >= now]
        past = [r for r in rows if r[1].start_time < now]

        lines = []
        if upcoming:
            lines.append("Upcoming appointments:")
            for appt, slot, doctor in upcoming:
                lines.append(
                    f"- appointment_id={appt.id} | {slot.start_time:%a %Y-%m-%d %H:%M} | "
                    f"{doctor.name} ({doctor.specialty}) | {appt.reason}"
                )
        if past:
            lines.append("Past visits (most recent first):")
            for appt, slot, doctor in reversed(past):
                note = f" | Notes: {appt.notes}" if appt.notes else ""
                lines.append(
                    f"- {slot.start_time:%Y-%m-%d} | {doctor.name} ({doctor.specialty}) | "
                    f"{appt.reason}{note}"
                )
        return "\n".join(lines)


@tool
def recommend_specialty(
    specialty: str, issue_summary: str, tool_call_id: ToolCallId
) -> str | Command:
    """Record the specialty that best fits the patient's concern, along with a
    one-sentence summary of the concern. The specialty must be one of the
    clinic's specialties."""
    valid = {s.lower(): s for s in list_specialties()}
    canonical = valid.get(specialty.strip().lower())
    if canonical is None:
        return f"Error: '{specialty}' isn't offered. Choose one of: {', '.join(valid.values())}."
    return _commit(
        tool_call_id,
        f"Recorded specialty {canonical}.",
        specialty=canonical,
        issue_summary=issue_summary.strip(),
    )


@tool
def find_doctors_with_availability(specialty: str) -> str:
    """List the doctors in a specialty with their next open appointment times."""
    now = datetime.now()
    with get_session() as session:
        doctors = session.query(Doctor).filter(Doctor.specialty.ilike(specialty.strip())).all()
        if not doctors:
            return f"No doctors found for specialty '{specialty}'."

        lines = []
        for doctor in doctors:
            slots = (
                session.query(AppointmentSlot)
                .filter(
                    AppointmentSlot.doctor_id == doctor.id,
                    AppointmentSlot.status == "open",
                    AppointmentSlot.start_time >= now,
                )
                .order_by(AppointmentSlot.start_time)
                .limit(3)
                .all()
            )
            openings = ", ".join(f"{s.start_time:%a %Y-%m-%d %H:%M}" for s in slots) or "none"
            lines.append(
                f"{doctor.id} | {doctor.name} | {doctor.specialty} | next openings: {openings}"
            )
        return "\n".join(lines)


@tool
def select_doctor(doctor_id: str, tool_call_id: ToolCallId) -> str | Command:
    """Record the doctor the patient chose to see."""
    with get_session() as session:
        doctor = session.get(Doctor, doctor_id)
        if doctor is None:
            return f"Error: no doctor with id '{doctor_id}'."
        return _commit(
            tool_call_id,
            f"Selected {doctor.name} ({doctor.specialty}).",
            doctor_id=doctor.id,
        )


@tool
def get_availability(doctor_id: str, start_date: str, end_date: str) -> str:
    """Get open appointment slots for a doctor within a date range.

    Args:
        doctor_id: The doctor's id, e.g. "D001".
        start_date: ISO date, e.g. "2026-09-14".
        end_date: ISO date, e.g. "2026-09-18".
    """
    with get_session() as session:
        doctor = session.get(Doctor, doctor_id)
        if doctor is None:
            return f"Error: no doctor with id '{doctor_id}'."

        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)
        except ValueError:
            return "Error: start_date/end_date must be ISO dates like '2026-09-14'."

        slots = (
            session.query(AppointmentSlot)
            .filter(
                AppointmentSlot.doctor_id == doctor_id,
                AppointmentSlot.status == "open",
                AppointmentSlot.start_time >= start,
                AppointmentSlot.start_time <= end,
            )
            .order_by(AppointmentSlot.start_time)
            .all()
        )
        if not slots:
            return f"No open slots for {doctor.name} between {start_date} and {end_date}."
        return "\n".join(
            f"{s.id} | {s.start_time:%a %Y-%m-%d %H:%M}-{s.end_time:%H:%M}" for s in slots
        )


@tool
def propose_booking(
    slot_id: str,
    reason: str = "",
    patient_id: PatientIdFromState = None,
    doctor_id: DoctorIdFromState = None,
) -> str:
    """Stage a booking for the patient into an open slot of their selected
    doctor, returning a pending_booking_id for the user to confirm via
    confirm_booking."""
    if not patient_id:
        return NOT_IDENTIFIED

    with get_session() as session:
        slot = session.get(AppointmentSlot, slot_id)
        if slot is None:
            return f"Error: no appointment slot with id '{slot_id}'."
        if slot.status != "open":
            return f"Error: slot {slot_id} is not open (status: {slot.status})."
        if doctor_id and slot.doctor_id != doctor_id:
            return (
                "Error: that slot belongs to a different doctor than the one selected. "
                "Call select_doctor to switch doctors first."
            )

        patient = session.get(Patient, patient_id)
        doctor = session.get(Doctor, slot.doctor_id)
        pending = PendingBooking(
            id=str(uuid.uuid4()),
            action="book",
            slot_id=slot_id,
            appointment_id=None,
            patient_id=patient_id,
            reason=reason,
            created_at=datetime.now(),
        )
        session.add(pending)
        session.flush()
        return (
            f"Proposed booking pending_booking_id={pending.id}: {patient.name} with "
            f"{doctor.name} on {slot.start_time:%A %Y-%m-%d %H:%M}. Ask the user to confirm, "
            f"then call confirm_booking with pending_booking_id='{pending.id}'."
        )


@tool
def confirm_booking(
    pending_booking_id: str,
    tool_call_id: ToolCallId,
    patient_id: PatientIdFromState = None,
) -> str | Command:
    """Confirm a previously proposed booking. Call this only after the user has
    explicitly confirmed (e.g. 'yes, book it')."""
    if not patient_id:
        return NOT_IDENTIFIED

    with get_session() as session:
        pending = session.get(PendingBooking, pending_booking_id)
        if pending is None or pending.action != "book" or pending.patient_id != patient_id:
            return f"Error: no pending booking with id '{pending_booking_id}'."

        slot = session.get(AppointmentSlot, pending.slot_id)
        if slot is None or slot.status != "open":
            return "Error: that slot is no longer open. Please propose a new booking."

        slot.status = "booked"
        appointment = Appointment(
            id=str(uuid.uuid4()),
            slot_id=slot.id,
            patient_id=patient_id,
            doctor_id=slot.doctor_id,
            created_at=datetime.now(),
            status="confirmed",
            reason=pending.reason,
        )
        session.add(appointment)
        session.delete(pending)
        session.flush()
        return _commit(
            tool_call_id,
            f"Booked. appointment_id={appointment.id}, {slot.start_time:%A %Y-%m-%d %H:%M}.",
            appointment_id=appointment.id,
        )


@tool
def propose_cancellation(
    appointment_id: str, reason: str = "", patient_id: PatientIdFromState = None
) -> str:
    """Stage cancelling one of the patient's appointments, returning a
    pending_booking_id for the user to confirm via confirm_cancellation."""
    if not patient_id:
        return NOT_IDENTIFIED

    with get_session() as session:
        appointment = session.get(Appointment, appointment_id)
        if (
            appointment is None
            or appointment.status != "confirmed"
            or appointment.patient_id != patient_id
        ):
            return f"Error: no active appointment with id '{appointment_id}' for this patient."

        pending = PendingBooking(
            id=str(uuid.uuid4()),
            action="cancel",
            slot_id=None,
            appointment_id=appointment_id,
            patient_id=patient_id,
            reason=reason,
            created_at=datetime.now(),
        )
        session.add(pending)
        session.flush()
        return (
            f"Proposed cancellation pending_booking_id={pending.id} for appointment "
            f"{appointment_id}. Ask the user to confirm, then call confirm_cancellation "
            f"with pending_booking_id='{pending.id}'."
        )


@tool
def confirm_cancellation(
    pending_booking_id: str, patient_id: PatientIdFromState = None
) -> str:
    """Confirm a previously proposed cancellation. Call this only after the
    user has explicitly confirmed."""
    if not patient_id:
        return NOT_IDENTIFIED

    with get_session() as session:
        pending = session.get(PendingBooking, pending_booking_id)
        if pending is None or pending.action != "cancel" or pending.patient_id != patient_id:
            return f"Error: no pending cancellation with id '{pending_booking_id}'."

        appointment = session.get(Appointment, pending.appointment_id)
        if appointment is None:
            return "Error: that appointment no longer exists."

        appointment.status = "cancelled"
        slot = session.get(AppointmentSlot, appointment.slot_id)
        if slot is not None:
            slot.status = "open"
        session.delete(pending)
        session.flush()
        return f"Cancelled appointment {appointment.id}."
