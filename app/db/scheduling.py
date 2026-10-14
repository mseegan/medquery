"""Scheduling database: the doctor directory and booked appointments."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings
from app.db.common import make_engine, make_factory, session_scope


class SchedulingBase(DeclarativeBase):
    pass


class Doctor(SchedulingBase):
    __tablename__ = "doctors"

    doctor_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    specialty: Mapped[str] = mapped_column(String, index=True)


class Appointment(SchedulingBase):
    """A booked slot: doctor name, doctor id, patient id, and date/time. Open
    times are not stored; see app.db.availability."""

    __tablename__ = "appointments"
    __table_args__ = (UniqueConstraint("doctor_id", "date"),)

    appointment_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doctor_name: Mapped[str] = mapped_column(String)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.doctor_id"), index=True)
    patient_id: Mapped[str] = mapped_column(String, index=True)
    date: Mapped[datetime] = mapped_column(DateTime)


engine = make_engine(settings.scheduling_db_path)
get_session = session_scope(make_factory(engine))


def init_scheduling_db() -> None:
    SchedulingBase.metadata.create_all(engine)


def reset_scheduling_db() -> None:
    SchedulingBase.metadata.drop_all(engine)
    SchedulingBase.metadata.create_all(engine)
