"""Tools for maintaining a patient's medical history in the records database.
Every write also refreshes the patient's summary and long-term memory."""
import uuid
from datetime import date

from langchain_core.tools import tool

from app.db import records
from app.memory.service import remember
from app.memory.summarizer import refresh_patient_summary
from app.tools.common import NOT_IDENTIFIED, PatientIdFromState

PROFILE_FIELDS = ("name", "gender", "phone", "email", "address")


def _refresh(patient_id: str) -> str:
    try:
        refresh_patient_summary(patient_id)
        return "Summary updated."
    except Exception as exc:  # the saved record stands even if the summary can't refresh
        return f"Saved, but the summary couldn't be refreshed ({exc})."


@tool
def add_history_entry(
    diagnosis: str,
    notes: str = "",
    icd10_code: str = "",
    chief_complaint: str = "",
    visit_date: str | None = None,
    patient_id: PatientIdFromState = None,
) -> str:
    """Add one diagnosis or condition to the identified patient's medical
    history, as reported by the patient or their caregiver. Make one entry per
    diagnosis and put its medications, avoided drugs, and other details in
    notes; don't make separate entries for those. Record only what they state.
    visit_date is YYYY-MM-DD and defaults to today."""
    if not patient_id:
        return NOT_IDENTIFIED

    when = date.today()
    if visit_date:
        try:
            when = date.fromisoformat(visit_date.strip())
        except ValueError:
            return "Error: visit_date must be an ISO date like 2026-03-12."

    code = f" ({icd10_code})" if icd10_code else ""
    with records.get_session() as session:
        patient = session.get(records.Patient, patient_id)
        session.add(
            records.Encounter(
                encounter_id=f"E{uuid.uuid4().hex[:8].upper()}",
                patient_id=patient_id,
                visit_date=when,
                provider="Patient-reported",
                chief_complaint=chief_complaint or "History update",
                subjective=notes,
                assessment=f"Diagnosis: {diagnosis}{code}",
                diagnosis=diagnosis,
                icd10_code=icd10_code,
            )
        )
        name = patient.name

    detail = f"{diagnosis}{code}" + (f": {notes}" if notes else "")
    remember(patient_id, f"Reported on {date.today()}: {detail}", source="history_agent")
    return f"Recorded {diagnosis} in {name}'s history. {_refresh(patient_id)}"


@tool
def update_patient_profile(
    name: str | None = None,
    dob: str | None = None,
    gender: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    address: str | None = None,
    patient_id: PatientIdFromState = None,
) -> str:
    """Update the identified patient's profile. Pass only the fields to change.
    dob is YYYY-MM-DD."""
    if not patient_id:
        return NOT_IDENTIFIED

    changes = {
        key: value.strip()
        for key, value in {
            "name": name,
            "gender": gender,
            "phone": phone,
            "email": email,
            "address": address,
        }.items()
        if value
    }
    parsed_dob = None
    if dob:
        try:
            parsed_dob = date.fromisoformat(dob.strip())
        except ValueError:
            return "Error: dob must be an ISO date like 1985-03-12."
    if not changes and not parsed_dob:
        return "Nothing to update."

    with records.get_session() as session:
        patient = session.get(records.Patient, patient_id)
        for key, value in changes.items():
            setattr(patient, key, value)
        if parsed_dob:
            patient.dob = parsed_dob

    updated = list(changes) + (["dob"] if parsed_dob else [])
    affects_summary = parsed_dob or "gender" in changes or "name" in changes
    note = _refresh(patient_id) if affects_summary else ""
    return f"Updated {', '.join(updated)}. {note}".strip()
