"""Read-only queries behind the UI, over the records and scheduling databases and
the patient memory."""
import re
from dataclasses import dataclass
from datetime import date, datetime

from app.db import records, scheduling
from app.memory.service import MEMORY, RECORD
from app.memory.vector_store import get_store


@dataclass
class ScheduleRow:
    appointment_id: int
    when: datetime
    patient_id: str
    patient_name: str
    concern: str


@dataclass
class PatientAppointment:
    appointment_id: int
    when: datetime
    doctor_name: str
    specialty: str


@dataclass
class PatientDetail:
    patient: records.Patient
    encounters: list[records.Encounter]  # newest first
    upcoming: list[PatientAppointment]
    notes: list[tuple[str, str]]  # (kind, text) from long-term memory


def list_doctors() -> list[scheduling.Doctor]:
    with scheduling.get_session() as session:
        return session.query(scheduling.Doctor).order_by(scheduling.Doctor.doctor_id).all()


def list_patients() -> list[records.Patient]:
    with records.get_session() as session:
        return session.query(records.Patient).order_by(records.Patient.name).all()


def get_patient(patient_id: str) -> records.Patient | None:
    with records.get_session() as session:
        return session.get(records.Patient, patient_id)


def _patient_names(patient_ids: set[str]) -> dict[str, str]:
    if not patient_ids:
        return {}
    with records.get_session() as session:
        rows = session.query(records.Patient).filter(records.Patient.patient_id.in_(patient_ids)).all()
    return {p.patient_id: p.name for p in rows}


def _booking_concerns(appointments: list[scheduling.Appointment]) -> dict[int, str]:
    """The concern each appointment was booked for, read from the memory note the
    planner saved when it was booked. Empty for appointments made another way."""
    ids = {f"{MEMORY}:{a.patient_id}:booked-{a.appointment_id}": a.appointment_id for a in appointments}
    if not ids:
        return {}
    found = get_store().get(ids=list(ids))
    concerns = {}
    for note_id, text in zip(found["ids"], found["documents"]):
        match = re.search(r" for (.+?)\.?$", text)
        if match:
            concerns[ids[note_id]] = match.group(1)
    return concerns


def doctor_schedule(doctor_id: str, include_past: bool = False) -> list[ScheduleRow]:
    with scheduling.get_session() as session:
        query = session.query(scheduling.Appointment).filter(scheduling.Appointment.doctor_id == doctor_id)
        if not include_past:
            query = query.filter(scheduling.Appointment.date >= datetime.now())
        appointments = query.order_by(scheduling.Appointment.date).all()

    names = _patient_names({a.patient_id for a in appointments})
    concerns = _booking_concerns(appointments)
    return [
        ScheduleRow(
            a.appointment_id,
            a.date,
            a.patient_id,
            names.get(a.patient_id, a.patient_id),
            concerns.get(a.appointment_id, ""),
        )
        for a in appointments
    ]


def patient_upcoming(patient_id: str) -> list[PatientAppointment]:
    with scheduling.get_session() as session:
        rows = (
            session.query(scheduling.Appointment, scheduling.Doctor)
            .join(scheduling.Doctor, scheduling.Appointment.doctor_id == scheduling.Doctor.doctor_id)
            .filter(
                scheduling.Appointment.patient_id == patient_id,
                scheduling.Appointment.date >= datetime.now(),
            )
            .order_by(scheduling.Appointment.date)
            .all()
        )
    return [PatientAppointment(a.appointment_id, a.date, d.name, d.specialty) for a, d in rows]


def patient_notes(patient_id: str) -> list[tuple[str, str]]:
    found = get_store().get(
        where={"$and": [{"patient_id": patient_id}, {"kind": {"$in": [RECORD, MEMORY]}}]}
    )
    notes = [(m["kind"], text, m["created_at"]) for m, text in zip(found["metadatas"], found["documents"])]
    return [(kind, text) for kind, text, _ in sorted(notes, key=lambda n: n[2], reverse=True)]


def patient_detail(patient_id: str) -> PatientDetail | None:
    patient = get_patient(patient_id)
    if patient is None:
        return None
    with records.get_session() as session:
        encounters = (
            session.query(records.Encounter)
            .filter(records.Encounter.patient_id == patient_id)
            .order_by(records.Encounter.visit_date.desc())
            .all()
        )
    return PatientDetail(patient, encounters, patient_upcoming(patient_id), patient_notes(patient_id))


def patient_age(patient: records.Patient) -> str:
    if patient.dob:
        today = date.today()
        years = today.year - patient.dob.year - (
            (today.month, today.day) < (patient.dob.month, patient.dob.day)
        )
        return f"{years}"
    return f"{patient.age}" if patient.age else "unknown"
