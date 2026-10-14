"""Builds both databases from the doctor roster (seed_data/doctors.json) and the
patient records folder (records.xlsx plus visit-note PDFs)."""
import json
from pathlib import Path

from app.config import settings
from app.db import records, scheduling
from app.db.loaders import load_patients_xlsx, parse_note_pdf

DOCTORS_FILE = Path(__file__).resolve().parents[2] / "seed_data" / "doctors.json"


def _data_dir(data_dir: str | None) -> Path:
    path = Path(data_dir or settings.records_data_dir or "")
    if not (path / "records.xlsx").is_file():
        raise SystemExit(
            "Set RECORDS_DATA_DIR in .env (or pass the folder as an argument) to the folder "
            "containing records.xlsx and the visit-note PDFs."
        )
    return path


def _seed_doctors() -> int:
    roster = json.loads(DOCTORS_FILE.read_text(encoding="utf-8"))
    with scheduling.get_session() as session:
        for doctor in roster:
            session.add(scheduling.Doctor(**doctor))
    return len(roster)


def _load_people(folder: Path) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """Patients keyed by lowercase name, and their visit encounters."""
    people = {p["name"].lower(): dict(p) for p in load_patients_xlsx(folder / "records.xlsx")}
    visits: dict[str, list[dict]] = {}

    for pdf in sorted(folder.glob("*.pdf")):
        details, encounters = parse_note_pdf(pdf)
        if not details.get("name"):
            continue
        person = people.setdefault(details["name"].lower(), {"name": details["name"]})
        for key in ("dob", "mrn", "gender", "phone", "address"):
            if details.get(key) and not person.get(key):
                person[key] = details[key]
        visits.setdefault(details["name"].lower(), []).extend(encounters)

    return people, visits


def _seed_patients(folder: Path) -> tuple[int, int]:
    people, visits = _load_people(folder)
    encounter_count = 0
    with records.get_session() as session:
        for number, (key, person) in enumerate(people.items(), start=1):
            patient_id = f"P{number:04d}"
            encounters = sorted(visits.get(key, []), key=lambda e: e["visit_date"])

            summary = person.get("summary", "")
            if not summary and encounters:
                diagnoses = [e["diagnosis"] for e in encounters if e["diagnosis"]]
                summary = f"History of {'; '.join(diagnoses)}."

            session.add(
                records.Patient(
                    patient_id=patient_id,
                    name=person["name"],
                    dob=person.get("dob"),
                    age=person.get("age"),
                    mrn=person.get("mrn", ""),
                    gender=person.get("gender", ""),
                    phone=person.get("phone", ""),
                    email=person.get("email", ""),
                    address=person.get("address", ""),
                    summary=summary,
                )
            )
            for encounter in encounters:
                encounter_count += 1
                session.add(
                    records.Encounter(
                        encounter_id=f"E{encounter_count:04d}",
                        patient_id=patient_id,
                        **encounter,
                    )
                )
    return len(people), encounter_count


def seed(data_dir: str | None = None) -> None:
    folder = _data_dir(data_dir)
    records.reset_records_db()
    scheduling.reset_scheduling_db()

    doctors = _seed_doctors()
    patients, encounters = _seed_patients(folder)
    print(f"Seeded {doctors} doctors, {patients} patients, and {encounters} visit notes.")


if __name__ == "__main__":
    seed()
