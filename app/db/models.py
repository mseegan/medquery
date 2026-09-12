from datetime import datetime, time

from sqlalchemy import ForeignKey, String, Time
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    specialty: Mapped[str] = mapped_column(String)
    bio: Mapped[str] = mapped_column(String, default="")


class AvailabilityTemplate(Base):
    """Clinic-wide recurring weekly availability: one row per bookable
    time-of-day window, applied to every business weekday (Mon-Fri) for
    every doctor. app.db.availability.generate_slots() expands these into
    concrete AppointmentSlot rows.
    """

    __tablename__ = "availability_templates"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    dob: Mapped[str] = mapped_column(String)  # ISO date string, e.g. "1985-03-12"
    mrn_fake: Mapped[str] = mapped_column(String)  # synthetic medical record number


class AppointmentSlot(Base):
    __tablename__ = "appointment_slots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"))
    start_time: Mapped[datetime] = mapped_column()
    end_time: Mapped[datetime] = mapped_column()
    status: Mapped[str] = mapped_column(String, default="open")  # "open" | "booked"


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    slot_id: Mapped[str] = mapped_column(ForeignKey("appointment_slots.id"), unique=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"))
    created_at: Mapped[datetime] = mapped_column()
    status: Mapped[str] = mapped_column(String, default="confirmed")  # "confirmed" | "cancelled"
    reason: Mapped[str] = mapped_column(String, default="")


class PendingBooking(Base):
    """A booking or cancellation staged by a propose_* tool call, completed
    by the matching confirm_* tool call once the user confirms."""

    __tablename__ = "pending_bookings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    action: Mapped[str] = mapped_column(String)  # "book" | "cancel"
    slot_id: Mapped[str | None] = mapped_column(ForeignKey("appointment_slots.id"), nullable=True)
    appointment_id: Mapped[str | None] = mapped_column(ForeignKey("appointments.id"), nullable=True)
    patient_id: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column()
