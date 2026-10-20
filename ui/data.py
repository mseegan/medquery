"""Read-only queries behind the UI, over the records and scheduling databases and
the patient memory."""
from dataclasses import dataclass
from datetime import date, datetime

from app.db import records, scheduling
from app.memory.service import get_store


@dataclass
class ScheduleRow:
    appointment_id: int
    when: datetime
    patient_id: str
    patient_name: str
    concern: str


def list_doctors() -> list[scheduling.Doctor]:
    with scheduling.get_session() as session:
        return session.query(scheduling.Doctor).order_by(scheduling.Doctor.doctor_id).all()
