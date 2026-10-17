"""Summarization chain: a patient's chart becomes a short clinical summary that
is saved to the records DB and the vector store."""
from datetime import date
from functools import lru_cache

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.config import settings
from app.db import records
from app.memory.service import get_imported, index_summary

PROMPT_FIELD_CHARS = 1500

SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You write patient summaries for a clinic's scheduling and care-coordination "
            "assistant. Summarize only what the chart below states; never add diagnoses, "
            "medications, or facts that are not in it. Write plain text, 120 words or fewer, "
            "in this order: who the patient is (age, sex); known conditions with ICD-10 codes "
            "when given, including past or chronic conditions that the notes mention in the "
            "patient's history even if they weren't the diagnosis that visit; current medications and treatments mentioned; the most recent visit "
            "(date and reason); and anything that matters when booking care. Entries marked "
            "[reported history] are things the patient or family reported, not clinic visits, so "
            "never call them visits. Skip any part the chart doesn't cover. Do not use markdown or emojis.",
        ),
        (
            "human",
            "Patient: {profile}\n\n"
            "Imported record summary: {imported}\n\n"
            "Visits (oldest first):\n{visits}\n\n"
            "Write the summary.",
        ),
    ]
)


@lru_cache
def summary_chain():
    model = ChatAnthropic(model=settings.haiku_model, api_key=settings.anthropic_api_key)
    return SUMMARY_PROMPT | model | StrOutputParser()


def _trim(text: str) -> str:
    return text if len(text) <= PROMPT_FIELD_CHARS else text[:PROMPT_FIELD_CHARS] + "..."


def _age(patient: records.Patient) -> str:
    if patient.dob:
        today = date.today()
        years = today.year - patient.dob.year - (
            (today.month, today.day) < (patient.dob.month, patient.dob.day)
        )
        return f"{years} years old"
    return f"{patient.age} years old" if patient.age else "age unknown"


def chart_inputs(patient_id: str, imported_summary: str = "") -> dict:
    """The chain's inputs, assembled from the patient's profile and visits."""
    with records.get_session() as session:
        patient = session.get(records.Patient, patient_id)
        encounters = (
            session.query(records.Encounter)
            .filter(records.Encounter.patient_id == patient_id)
            .order_by(records.Encounter.visit_date)
            .all()
        )

    visits = [
        f"- {e.visit_date} | "
        + ("[reported history, not a clinic visit]" if e.provider == "Patient-reported" else e.provider or "provider unknown")
        + " | "
        f"Complaint: {e.chief_complaint or 'n/a'} | Diagnosis: {e.diagnosis} ({e.icd10_code}) | "
        f"Subjective: {_trim(e.subjective)} | Objective: {_trim(e.objective)} | "
        f"Plan: {_trim(e.plan)}"
        for e in encounters
    ]
    return {
        "profile": f"{patient.name}, {_age(patient)}, {patient.gender or 'sex unknown'}",
        "imported": imported_summary or "none",
        "visits": "\n".join(visits) or "none on file",
    }


def summarize_patient(patient_id: str, imported_summary: str = "") -> str:
    return summary_chain().invoke(chart_inputs(patient_id, imported_summary)).strip()


def refresh_patient_summary(patient_id: str, imported_summary: str = "") -> str:
    """Regenerate the summary from the chart, save it on the patient, and
    replace the one in the vector store."""
    summary = summarize_patient(patient_id, imported_summary or get_imported(patient_id))
    with records.get_session() as session:
        session.get(records.Patient, patient_id).summary = summary
    index_summary(patient_id, summary)
    return summary
