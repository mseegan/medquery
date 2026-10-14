"""Doctor availability: clinic hours minus a doctor's booked appointments."""
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.db.scheduling import Appointment

WORK_DAYS = {0, 1, 2, 3, 4}  # Monday-Friday
DAY_PARTS = [(time(9, 0), time(12, 0)), (time(13, 0), time(17, 0))]  # lunch 12-1
SLOT_MINUTES = 30
SEARCH_HORIZON_DAYS = 60


def slots_on(day: date) -> list[datetime]:
    """Every bookable start time on a given day, ignoring existing bookings."""
    if day.weekday() not in WORK_DAYS:
        return []
    slots = []
    for start, end in DAY_PARTS:
        cursor = datetime.combine(day, start)
        close = datetime.combine(day, end)
        while cursor < close:
            slots.append(cursor)
            cursor += timedelta(minutes=SLOT_MINUTES)
    return slots


def open_slots(
    session: Session, doctor_id: str, start: datetime, end: datetime
) -> list[datetime]:
    """Future slots for a doctor between start and end that nobody has booked."""
    booked = {
        row[0]
        for row in session.query(Appointment.date)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.date >= start,
            Appointment.date <= end,
        )
        .all()
    }
    now = datetime.now()
    result = []
    day = start.date()
    while day <= end.date():
        for slot in slots_on(day):
            if slot > now and start <= slot <= end and slot not in booked:
                result.append(slot)
        day += timedelta(days=1)
    return result


def next_openings(session: Session, doctor_id: str, count: int = 3) -> list[datetime]:
    """The doctor's earliest open slots, searching up to SEARCH_HORIZON_DAYS out."""
    now = datetime.now()
    found: list[datetime] = []
    day = now.date()
    for _ in range(SEARCH_HORIZON_DAYS):
        end = datetime.combine(day, time.max)
        found += open_slots(session, doctor_id, datetime.combine(day, time.min), end)
        if len(found) >= count:
            break
        day += timedelta(days=1)
    return found[:count]


def is_open(session: Session, doctor_id: str, slot: datetime) -> bool:
    return slot in open_slots(session, doctor_id, slot, slot)
