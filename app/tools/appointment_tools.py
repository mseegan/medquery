import uuid
from datetime import datetime

from langchain_core.tools import tool

from app.db.database import get_session
from app.db.models import Appointment, AppointmentSlot, Doctor, Patient, PendingBooking


def _fmt_slot(slot: AppointmentSlot) -> str:
    return f"{slot.id} | {slot.start_time:%Y-%m-%d %H:%M}-{slot.end_time:%H:%M} | {slot.status}"


@tool
def list_doctors(specialty: str | None = None) -> str:
    """List doctors, optionally filtered by specialty (e.g. 'Cardiology')."""
    with get_session() as session:
        query = session.query(Doctor)
        if specialty:
            query = query.filter(Doctor.specialty.ilike(f"%{specialty}%"))
        doctors = query.all()
        if not doctors:
            return f"No doctors found for specialty '{specialty}'." if specialty else "No doctors found."
        return "\n".join(f"{d.id} | {d.name} | {d.specialty}" for d in doctors)


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
        return "\n".join(_fmt_slot(s) for s in slots)


@tool
def propose_booking(slot_id: str, patient_id: str, reason: str = "") -> str:
    """Propose booking a patient into an open appointment slot.

    This does NOT actually book the appointment — it stages the booking and
    returns a pending_booking_id. The user must explicitly confirm before
    confirm_booking is called with that id.
    """
    with get_session() as session:
        slot = session.get(AppointmentSlot, slot_id)
        if slot is None:
            return f"Error: no appointment slot with id '{slot_id}'."
        if slot.status != "open":
            return f"Error: slot {slot_id} is not open (status: {slot.status})."
        patient = session.get(Patient, patient_id)
        if patient is None:
            return f"Error: no patient with id '{patient_id}'."

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
        doctor = session.get(Doctor, slot.doctor_id)
        return (
            f"Proposed booking pending_booking_id={pending.id}: {patient.name} with {doctor.name} "
            f"on {slot.start_time:%Y-%m-%d %H:%M}. Ask the user to confirm, then call "
            f"confirm_booking with pending_booking_id='{pending.id}'."
        )


@tool
def confirm_booking(pending_booking_id: str) -> str:
    """Confirm a previously proposed booking. Only call this after the user
    has explicitly confirmed (e.g. 'yes, book it')."""
    with get_session() as session:
        pending = session.get(PendingBooking, pending_booking_id)
        if pending is None or pending.action != "book":
            return f"Error: no pending booking with id '{pending_booking_id}'."

        slot = session.get(AppointmentSlot, pending.slot_id)
        if slot is None or slot.status != "open":
            return "Error: that slot is no longer open. Please propose a new booking."

        slot.status = "booked"
        appointment = Appointment(
            id=str(uuid.uuid4()),
            slot_id=slot.id,
            patient_id=pending.patient_id,
            doctor_id=slot.doctor_id,
            created_at=datetime.now(),
            status="confirmed",
            reason=pending.reason,
        )
        session.add(appointment)
        session.delete(pending)
        session.flush()
        return f"Booked. appointment_id={appointment.id}, {slot.start_time:%Y-%m-%d %H:%M}."


@tool
def propose_cancellation(appointment_id: str, reason: str = "") -> str:
    """Propose cancelling an existing appointment. Stages the cancellation and
    returns a pending_booking_id; the user must confirm before
    confirm_cancellation is called."""
    with get_session() as session:
        appointment = session.get(Appointment, appointment_id)
        if appointment is None or appointment.status != "confirmed":
            return f"Error: no active appointment with id '{appointment_id}'."

        pending = PendingBooking(
            id=str(uuid.uuid4()),
            action="cancel",
            slot_id=None,
            appointment_id=appointment_id,
            patient_id=appointment.patient_id,
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
def confirm_cancellation(pending_booking_id: str) -> str:
    """Confirm a previously proposed cancellation. Only call this after the
    user has explicitly confirmed."""
    with get_session() as session:
        pending = session.get(PendingBooking, pending_booking_id)
        if pending is None or pending.action != "cancel":
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


@tool
def get_patient_appointments(patient_id: str) -> str:
    """List a patient's upcoming confirmed appointments."""
    with get_session() as session:
        patient = session.get(Patient, patient_id)
        if patient is None:
            return f"Error: no patient with id '{patient_id}'."

        appointments = (
            session.query(Appointment)
            .filter(Appointment.patient_id == patient_id, Appointment.status == "confirmed")
            .all()
        )
        if not appointments:
            return f"{patient.name} has no upcoming appointments."

        lines = []
        for appt in appointments:
            slot = session.get(AppointmentSlot, appt.slot_id)
            doctor = session.get(Doctor, appt.doctor_id)
            lines.append(
                f"{appt.id} | {doctor.name} | {slot.start_time:%Y-%m-%d %H:%M} | {appt.reason}"
            )
        return "\n".join(lines)


APPOINTMENT_TOOLS = [
    list_doctors,
    get_availability,
    propose_booking,
    confirm_booking,
    propose_cancellation,
    confirm_cancellation,
    get_patient_appointments,
]
