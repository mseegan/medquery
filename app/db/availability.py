import uuid
from datetime import date, datetime, time, timedelta
from typing import Sequence

from sqlalchemy.orm import Session

from app.db.models import AppointmentSlot, AvailabilityTemplate, Doctor

DEFAULT_TEMPLATE_WINDOWS: list[tuple[str, str]] = [
    ("09:00", "10:20"),
    ("10:20", "11:40"),
    ("11:40", "13:00"),
    ("13:00", "14:20"),
    ("14:20", "15:40"),
    ("15:40", "17:00"),
]


def ensure_template(session: Session) -> list[AvailabilityTemplate]:
    """Idempotently make sure the 6 clinic-wide template rows exist. Safe to
    call on every run (seed, extend, or app startup). Only inserts when the
    table is empty — does not reconcile existing rows against
    DEFAULT_TEMPLATE_WINDOWS if the constants are edited later."""
    existing = (
        session.query(AvailabilityTemplate)
        .order_by(AvailabilityTemplate.start_time)
        .all()
    )
    if existing:
        return existing
    rows = []
    for i, (start_s, end_s) in enumerate(DEFAULT_TEMPLATE_WINDOWS, start=1):
        row = AvailabilityTemplate(
            id=f"TPL-{i}",
            start_time=time.fromisoformat(start_s),
            end_time=time.fromisoformat(end_s),
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def business_days(start: date, count: int) -> list[date]:
    """Next `count` Mon-Fri dates starting at `start` (inclusive)."""
    days: list[date] = []
    cursor = start
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def generate_slots(
    session: Session,
    *,
    start_date: date | None = None,
    num_business_days: int = 14,
    doctor_ids: Sequence[str] | None = None,
) -> list[AppointmentSlot]:
    """Expand the clinic-wide AvailabilityTemplate into concrete
    AppointmentSlot rows for every business weekday in the window starting
    at start_date (default: tomorrow) x every doctor in doctor_ids (default:
    all doctors). Idempotent: a (doctor_id, start_time) pair that already
    has an AppointmentSlot row is skipped, so this is safe to call
    repeatedly or on overlapping ranges without creating duplicates. Returns
    the newly created rows."""
    template_rows = ensure_template(session)
    if not template_rows:
        return []

    doctors_q = session.query(Doctor)
    if doctor_ids is not None:
        doctors_q = doctors_q.filter(Doctor.id.in_(doctor_ids))
    doctors = doctors_q.all()
    if not doctors:
        return []

    if start_date is None:
        start_date = (datetime.now() + timedelta(days=1)).date()
    days = business_days(start_date, num_business_days)
    if not days:
        return []

    range_start = datetime.combine(days[0], time.min)
    range_end = datetime.combine(days[-1], time.max)
    existing = (
        session.query(AppointmentSlot.doctor_id, AppointmentSlot.start_time)
        .filter(
            AppointmentSlot.doctor_id.in_([d.id for d in doctors]),
            AppointmentSlot.start_time >= range_start,
            AppointmentSlot.start_time <= range_end,
        )
        .all()
    )
    seen = set(existing)

    created: list[AppointmentSlot] = []
    for doctor in doctors:
        for day in days:
            for tmpl in template_rows:
                slot_start = datetime.combine(day, tmpl.start_time)
                key = (doctor.id, slot_start)
                if key in seen:
                    continue
                slot = AppointmentSlot(
                    id=str(uuid.uuid4()),
                    doctor_id=doctor.id,
                    start_time=slot_start,
                    end_time=datetime.combine(day, tmpl.end_time),
                    status="open",
                )
                session.add(slot)
                created.append(slot)
                seen.add(key)

    session.flush()
    return created
