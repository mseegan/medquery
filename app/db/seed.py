import random
import uuid
from datetime import datetime, timedelta

from faker import Faker

from app.db.availability import generate_slots
from app.db.database import get_session, reset_db
from app.db.models import Appointment, Doctor, Patient

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
PRE_BOOKED_RATIO = 0.3


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

        tomorrow = (datetime.now() + timedelta(days=1)).date()
        created_slots = generate_slots(session, start_date=tomorrow, num_business_days=SLOT_DAYS_AHEAD)

        pre_booked = 0
        for slot in created_slots:
            if random.random() < PRE_BOOKED_RATIO:
                slot.status = "booked"
                pre_booked += 1
                patient = random.choice(patients)
                session.add(
                    Appointment(
                        id=str(uuid.uuid4()),
                        slot_id=slot.id,
                        patient_id=patient.id,
                        doctor_id=slot.doctor_id,
                        created_at=datetime.now(),
                        status="confirmed",
                        reason=random.choice(
                            ["Annual checkup", "Follow-up", "New patient consult", "Lab review"]
                        ),
                    )
                )

    print(f"Seeded {len(doctors)} doctors, {len(patients)} patients, "
          f"{len(created_slots)} appointment slots ({pre_booked} pre-booked).")


if __name__ == "__main__":
    seed()
