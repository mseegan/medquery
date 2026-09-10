import random
import uuid
from datetime import datetime, timedelta

from faker import Faker

from app.db.database import get_session, reset_db
from app.db.models import Appointment, AppointmentSlot, Doctor, Patient

fake = Faker()

SPECIALTIES = [
    "Family Medicine",
    "Cardiology",
    "Pediatrics",
    "Dermatology",
    "Psychiatry",
    "Orthopedics",
    "Neurology",
    "Endocrinology",
]

NUM_PATIENTS = 30
SLOT_DAYS_AHEAD = 14
SLOT_START_HOUR = 9
SLOT_END_HOUR = 17
SLOT_MINUTES = 30
PRE_BOOKED_RATIO = 0.3


def _business_days(start: datetime, count: int) -> list[datetime]:
    days = []
    cursor = start
    while len(days) < count:
        if cursor.weekday() < 5:  # Mon-Fri
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def seed(reset: bool = True) -> None:
    if reset:
        reset_db()

    with get_session() as session:
        doctors = []
        for i, specialty in enumerate(SPECIALTIES, start=1):
            doctor = Doctor(
                id=f"D{i:03d}",
                name=f"Dr. {fake.last_name()}",
                specialty=specialty,
                bio=f"{specialty} physician with {random.randint(3, 25)} years of experience.",
            )
            doctors.append(doctor)
            session.add(doctor)

        patients = []
        for i in range(1, NUM_PATIENTS + 1):
            dob = fake.date_of_birth(minimum_age=1, maximum_age=90)
            patient = Patient(
                id=f"P{i:03d}",
                name=fake.name(),
                dob=dob.isoformat(),
                mrn_fake=f"MRN-{fake.unique.random_number(digits=6, fix_len=True)}",
            )
            patients.append(patient)
            session.add(patient)

        session.flush()

        tomorrow = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        business_days = _business_days(tomorrow, SLOT_DAYS_AHEAD)

        for doctor in doctors:
            for day in business_days:
                slot_time = day.replace(hour=SLOT_START_HOUR)
                end_of_day = day.replace(hour=SLOT_END_HOUR)
                while slot_time < end_of_day:
                    slot = AppointmentSlot(
                        id=str(uuid.uuid4()),
                        doctor_id=doctor.id,
                        start_time=slot_time,
                        end_time=slot_time + timedelta(minutes=SLOT_MINUTES),
                        status="open",
                    )
                    session.add(slot)

                    if random.random() < PRE_BOOKED_RATIO:
                        slot.status = "booked"
                        patient = random.choice(patients)
                        session.add(
                            Appointment(
                                id=str(uuid.uuid4()),
                                slot_id=slot.id,
                                patient_id=patient.id,
                                doctor_id=doctor.id,
                                created_at=datetime.now(),
                                status="confirmed",
                                reason=random.choice(
                                    ["Annual checkup", "Follow-up", "New patient consult", "Lab review"]
                                ),
                            )
                        )

                    slot_time += timedelta(minutes=SLOT_MINUTES)

    print(f"Seeded {len(doctors)} doctors, {len(patients)} patients, "
          f"{len(doctors) * len(business_days)} slot-days.")


if __name__ == "__main__":
    seed()
