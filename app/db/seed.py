import random
import uuid
from datetime import datetime, time, timedelta

from faker import Faker

from app.db.availability import DEFAULT_TEMPLATE_WINDOWS, generate_slots
from app.db.database import get_session, reset_db
from app.db.models import Appointment, AppointmentSlot, Doctor, Patient

fake = Faker()

# Repeated specialties give the routing step more than one doctor to choose from.
SPECIALTIES = [
    "Family Medicine",
    "Family Medicine",
    "Cardiology",
    "Cardiology",
    "Pediatrics",
    "Pediatrics",
    "Dermatology",
    "Psychiatry",
    "Orthopedics",
    "Neurology",
    "Endocrinology",
]

NUM_PATIENTS = 30
SLOT_DAYS_AHEAD = 14
PRE_BOOKED_RATIO = 0.15
MAX_UPCOMING_PER_PATIENT = 3
MAX_PAST_VISITS_PER_PATIENT = 3
PAST_VISIT_REASONS = ["Annual checkup", "Follow-up", "New patient consult", "Lab review"]
PAST_VISIT_NOTES = [
    "Routine visit, no concerns. Continue current plan.",
    "Discussed lifestyle changes; follow up in 6 months.",
    "Lab work ordered; results reviewed and within normal range.",
    "Medication reviewed and refilled.",
    "Symptoms improving; return if they worsen.",
]


def _seed_past_visits(session, doctors, patients) -> int:
    """Give each patient up to MAX_PAST_VISITS_PER_PATIENT completed visits
    over the last ~6 months so the records lookup has history to show."""
    today = datetime.now().date()
    created = 0
    for patient in patients:
        for _ in range(random.randint(0, MAX_PAST_VISITS_PER_PATIENT)):
            day = today - timedelta(days=random.randint(7, 180))
            while day.weekday() >= 5:
                day -= timedelta(days=1)
            start_s, end_s = random.choice(DEFAULT_TEMPLATE_WINDOWS)
            doctor = random.choice(doctors)
            slot = AppointmentSlot(
                id=str(uuid.uuid4()),
                doctor_id=doctor.id,
                start_time=datetime.combine(day, time.fromisoformat(start_s)),
                end_time=datetime.combine(day, time.fromisoformat(end_s)),
                status="booked",
            )
            session.add(slot)
            session.add(
                Appointment(
                    id=str(uuid.uuid4()),
                    slot_id=slot.id,
                    patient_id=patient.id,
                    doctor_id=doctor.id,
                    created_at=datetime.combine(day, time.min),
                    status="completed",
                    reason=random.choice(PAST_VISIT_REASONS),
                    notes=random.choice(PAST_VISIT_NOTES),
                )
            )
            created += 1
    return created


def seed(reset: bool = True) -> None:
    if reset:
        reset_db()

    with get_session() as session:
        doctors = []
        for i, specialty in enumerate(SPECIALTIES, start=1):
            doctor = Doctor(
                id=f"D{i:03d}",
                name=f"Dr. {fake.unique.last_name()}",
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
        upcoming_counts = {p.id: 0 for p in patients}
        for slot in created_slots:
            if random.random() < PRE_BOOKED_RATIO:
                eligible = [p for p in patients if upcoming_counts[p.id] < MAX_UPCOMING_PER_PATIENT]
                if not eligible:
                    break
                patient = random.choice(eligible)
                upcoming_counts[patient.id] += 1
                slot.status = "booked"
                pre_booked += 1
                session.add(
                    Appointment(
                        id=str(uuid.uuid4()),
                        slot_id=slot.id,
                        patient_id=patient.id,
                        doctor_id=slot.doctor_id,
                        created_at=datetime.now(),
                        status="confirmed",
                        reason=random.choice(PAST_VISIT_REASONS),
                    )
                )

        past_visits = _seed_past_visits(session, doctors, patients)

    print(f"Seeded {len(doctors)} doctors, {len(patients)} patients, "
          f"{len(created_slots)} appointment slots ({pre_booked} pre-booked), "
          f"{past_visits} past visits.")


if __name__ == "__main__":
    seed()
