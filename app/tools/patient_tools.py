from datetime import date, datetime

from langchain_core.tools import tool
from sqlalchemy import func

from app.db import records, scheduling
from app.tools.common import NOT_IDENTIFIED, PatientIdFromState, ToolCallId, commit

RECENT_ENCOUNTERS = 5
PLAN_PREVIEW_CHARS = 240


def _age(patient: records.Patient) -> str:
    if patient.dob is None:
        return f"{patient.age} years old" if patient.age else "age unknown"
    today = date.today()
    dob = patient.dob
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return f"{years} years old"


@tool
def identify_patient(
    first_name: str,
    last_name: str,
    tool_call_id: ToolCallId,
    dob: str | None = None,
) -> str:
    """Identify the patient from their first and last name, creating a new
    patient record if none exists. If several patients share the name, this
    asks for a date of birth (YYYY-MM-DD); call it again with dob set."""
    full_name = f"{first_name.strip()} {last_name.strip()}".strip()

    parsed_dob = None
    if dob:
        try:
            parsed_dob = date.fromisoformat(dob.strip())
        except ValueError:
            return "Error: dob must be an ISO date like 1985-03-12."

    with records.get_session() as session:
        matches = (
            session.query(records.Patient)
            .filter(records.Patient.name.ilike(full_name))
            .all()
        )
        if parsed_dob:
            matches = [p for p in matches if p.dob == parsed_dob]

        if len(matches) > 1:
            return (
                "Several patients share that name. Ask the user for their date of "
                "birth (YYYY-MM-DD) and call identify_patient again with dob set."
            )

        if len(matches) == 1:
            patient = matches[0]
            message = f"Found existing patient {patient.name}."
        else:
            next_number = session.query(func.count(records.Patient.patient_id)).scalar() + 1
            patient = records.Patient(
                patient_id=f"P{next_number:04d}", name=full_name, dob=parsed_dob
            )
            session.add(patient)
            session.flush()
            message = f"Created a new patient record for {patient.name}."

        return commit(
            tool_call_id, message, patient_id=patient.patient_id, patient_name=patient.name
        )


@tool
def get_patient_history(patient_id: PatientIdFromState = None) -> str:
    """Get the identified patient's profile, recent past visits (with
    diagnoses), and upcoming appointments."""
    if not patient_id:
        return NOT_IDENTIFIED

    with records.get_session() as session:
        patient = session.get(records.Patient, patient_id)
        encounters = (
            session.query(records.Encounter)
            .filter(records.Encounter.patient_id == patient_id)
            .order_by(records.Encounter.visit_date.desc())
            .limit(RECENT_ENCOUNTERS)
            .all()
        )

    lines = [
        f"{patient.name}, {_age(patient)}"
        + (f", {patient.gender}" if patient.gender else ""),
        f"Summary: {patient.summary or 'none on file'}",
    ]

    if encounters:
        lines.append("Recent visits (newest first):")
        for e in encounters:
            code = f" ({e.icd10_code})" if e.icd10_code else ""
            plan = e.plan if len(e.plan) <= PLAN_PREVIEW_CHARS else e.plan[:PLAN_PREVIEW_CHARS] + "..."
            details = [e.provider, e.chief_complaint, f"{e.diagnosis}{code}", f"Plan: {plan}"]
            lines.append(f"- {e.visit_date} | " + " | ".join(d for d in details if d.strip()))
    else:
        lines.append("No past visits on file.")

    with scheduling.get_session() as session:
        upcoming = (
            session.query(scheduling.Appointment)
            .filter(
                scheduling.Appointment.patient_id == patient_id,
                scheduling.Appointment.date >= datetime.now(),
            )
            .order_by(scheduling.Appointment.date)
            .all()
        )
    if upcoming:
        lines.append("Upcoming appointments:")
        for a in upcoming:
            lines.append(f"- {a.date:%a %Y-%m-%d %H:%M} with {a.doctor_name}")

    return "\n".join(lines)
