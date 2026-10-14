"""Builds the vector store from the seeded databases and the records spreadsheet."""
from pathlib import Path

from app.config import settings
from app.db import records
from app.db.loaders import load_patients_xlsx
from app.memory.service import index_record
from app.memory.summarizer import refresh_patient_summary
from app.memory.vector_store import get_store

RECORDS_SOURCE = "records.xlsx"


def rebuild_memory(data_dir: str | None = None) -> tuple[int, int]:
    """Clear the vector store, index each spreadsheet record, then generate and
    index every patient's summary. Returns (records indexed, summaries made)."""
    folder = Path(data_dir or settings.records_data_dir)
    get_store().reset_collection()

    with records.get_session() as session:
        ids_by_name = {p.name.lower(): p.patient_id for p in session.query(records.Patient).all()}

    imported: dict[str, str] = {}
    for row in load_patients_xlsx(folder / RECORDS_SOURCE):
        patient_id = ids_by_name.get(row["name"].lower())
        if patient_id and row["summary"]:
            index_record(patient_id, row["summary"], RECORDS_SOURCE)
            imported[patient_id] = row["summary"]

    for patient_id in ids_by_name.values():
        refresh_patient_summary(patient_id, imported.get(patient_id, ""))

    return len(imported), len(ids_by_name)
