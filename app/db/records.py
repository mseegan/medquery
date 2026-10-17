"""Patient records database: who the patients are and their visit history."""
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings
from app.db.common import make_engine, make_factory, session_scope


class RecordsBase(DeclarativeBase):
    pass


class Patient(RecordsBase):
    __tablename__ = "patients"

    patient_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    age: Mapped[int | None] = mapped_column(nullable=True)  # as recorded, when dob is unknown
    mrn: Mapped[str] = mapped_column(String, default="")
    gender: Mapped[str] = mapped_column(String, default="")
    phone: Mapped[str] = mapped_column(String, default="")
    email: Mapped[str] = mapped_column(String, default="")
    address: Mapped[str] = mapped_column(String, default="")
    summary: Mapped[str] = mapped_column(Text, default="")


class Encounter(RecordsBase):
    """One past visit, laid out like a SOAP note."""

    __tablename__ = "encounters"

    encounter_id: Mapped[str] = mapped_column(String, primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id"), index=True)
    visit_date: Mapped[date] = mapped_column(Date)
    provider: Mapped[str] = mapped_column(String, default="")
    chief_complaint: Mapped[str] = mapped_column(String, default="")
    subjective: Mapped[str] = mapped_column(Text, default="")
    objective: Mapped[str] = mapped_column(Text, default="")
    assessment: Mapped[str] = mapped_column(Text, default="")
    plan: Mapped[str] = mapped_column(Text, default="")
    diagnosis: Mapped[str] = mapped_column(String, default="")
    icd10_code: Mapped[str] = mapped_column(String, default="")


engine = make_engine(settings.records_db_path)
get_session = session_scope(make_factory(engine))


def init_records_db() -> None:
    RecordsBase.metadata.create_all(engine)


def reset_records_db() -> None:
    RecordsBase.metadata.drop_all(engine)
    RecordsBase.metadata.create_all(engine)
