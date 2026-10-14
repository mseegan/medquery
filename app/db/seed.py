"""Builds both databases with synthetic doctors, patients, visit history, and
booked appointments."""
import random
from datetime import date, datetime, timedelta

from faker import Faker

from app.db import records, scheduling
from app.db.availability import open_slots

SEED = 7
NUM_PATIENTS = 40
MAX_UPCOMING_PER_PATIENT = 2

DOCTOR_SPECIALTIES = [
    "Family Medicine",
    "Family Medicine",
    "Internal Medicine",
    "Cardiology",
    "Cardiology",
    "Endocrinology",
    "Nephrology",
    "Nephrology",
    "Pulmonology",
    "Dermatology",
    "Neurology",
    "Psychiatry",
    "Orthopedics",
    "Obstetrics and Gynecology",
    "Pediatrics",
]

# Past-visit templates. "specialties" lists who typically sees the condition.
CONDITIONS = [
    {
        "diagnosis": "Type 2 Diabetes Mellitus",
        "icd10": "E11.9",
        "complaint": "Diabetes follow-up",
        "specialties": ["Endocrinology", "Family Medicine", "Internal Medicine"],
        "subjective": "Follow-up for type 2 diabetes. Reports increased thirst and urination over the past week. Diet and exercise unchanged.",
        "objective": "BP 140/88, pulse 82, temp 98.7F. Exam unremarkable. No foot ulcers.",
        "plan": "Adjust metformin dosage. Order HbA1c and lipid profile. Nutritionist follow-up. Return in 3 months.",
    },
    {
        "diagnosis": "Essential Hypertension",
        "icd10": "I10",
        "complaint": "Routine blood pressure check",
        "specialties": ["Cardiology", "Internal Medicine", "Family Medicine"],
        "subjective": "Routine checkup with a history of hypertension. No current complaints. Takes medication regularly.",
        "objective": "BP 130/84, pulse 76, temp 98.4F. Cardiovascular and respiratory exams normal. No peripheral edema.",
        "plan": "Continue current medication. Recommend lifestyle modifications. Routine labs ordered. Return in 6 months.",
    },
    {
        "diagnosis": "Upper Respiratory Infection",
        "icd10": "J06.9",
        "complaint": "Cough and mild fever",
        "specialties": ["Family Medicine", "Internal Medicine"],
        "subjective": "Five-day history of dry cough and mild fever. Denies shortness of breath. Partial relief with acetaminophen.",
        "objective": "BP 118/76, pulse 96, temp 100.2F. Mild pharyngeal erythema. Chest clear to auscultation.",
        "plan": "Symptomatic management with antihistamines and fluids. Rest. Follow up in 5 days if no improvement.",
    },
    {
        "diagnosis": "Costochondritis",
        "icd10": "M94.0",
        "complaint": "Sharp chest pain",
        "specialties": ["Family Medicine", "Internal Medicine"],
        "subjective": "Sharp pain at the sternum since this morning, worse with deep breaths or movement. Denies dizziness, palpitations, or shortness of breath. Started working out last week.",
        "objective": "Lungs clear. Heart regular rate and rhythm. Reproducible tenderness at the costosternal joint.",
        "plan": "Ibuprofen with food for 5-7 days. Mild stretching and rest. Red-flag symptoms reviewed. Follow up as needed.",
    },
    {
        "diagnosis": "Well adult exam",
        "icd10": "Z00.00",
        "complaint": "Annual wellness visit",
        "specialties": ["Family Medicine", "Internal Medicine"],
        "subjective": "Presents for annual exam. No concerns today. Diet and sleep are good; exercises a few times a week.",
        "objective": "Well-appearing, no acute distress. Vitals within normal limits. Exam unremarkable.",
        "plan": "Screening labs ordered. Vaccines up to date. Encouraged healthy lifestyle. Follow up in 1 year.",
    },
    {
        "diagnosis": "Migraine",
        "icd10": "G43.909",
        "complaint": "Recurrent headaches",
        "specialties": ["Neurology", "Family Medicine"],
        "subjective": "Throbbing headaches several times a month, sometimes with light sensitivity and nausea. Relief with rest in a dark room.",
        "objective": "Neurologic exam non-focal. Cranial nerves intact. No papilledema.",
        "plan": "Trial of abortive medication. Keep a headache diary. Avoid known triggers. Return in 2 months.",
    },
    {
        "diagnosis": "Low back pain",
        "icd10": "M54.50",
        "complaint": "Lower back pain",
        "specialties": ["Orthopedics", "Family Medicine"],
        "subjective": "Lower back pain for two weeks after lifting. Aching, worse with bending. No numbness or weakness in the legs.",
        "objective": "Paraspinal tenderness. Full range of motion with discomfort. Strength 5/5, straight-leg raise negative.",
        "plan": "NSAIDs as needed, heat, and gentle stretching. Physical therapy referral if not improved in 4 weeks.",
    },
    {
        "diagnosis": "Atopic dermatitis",
        "icd10": "L20.9",
        "complaint": "Itchy rash",
        "specialties": ["Dermatology", "Family Medicine"],
        "subjective": "Itchy, dry, red patches on the arms for several weeks. Worse in cold weather. No new soaps or medications.",
        "objective": "Erythematous scaly patches on the flexor surfaces. No signs of infection.",
        "plan": "Topical corticosteroid twice daily for 2 weeks. Fragrance-free moisturizer. Follow up in 4 weeks.",
    },
    {
        "diagnosis": "Asthma",
        "icd10": "J45.909",
        "complaint": "Wheezing and cough",
        "specialties": ["Pulmonology", "Family Medicine", "Internal Medicine"],
        "subjective": "Wheezing and night-time cough, worse with exercise and cold air. Uses rescue inhaler a few times a week.",
        "objective": "Scattered end-expiratory wheezes. Oxygen saturation 97% on room air.",
        "plan": "Start daily controller inhaler. Review inhaler technique. Peak flow monitoring. Return in 6 weeks.",
    },
    {
        "diagnosis": "Anxiety disorder",
        "icd10": "F41.9",
        "complaint": "Feeling anxious",
        "specialties": ["Psychiatry", "Family Medicine"],
        "subjective": "Several months of persistent worry, trouble sleeping, and muscle tension. No thoughts of self-harm.",
        "objective": "Anxious but cooperative. Speech and thought process normal. GAD-7 score 12.",
        "plan": "Start counseling referral and discuss medication options. Sleep hygiene reviewed. Return in 4 weeks.",
    },
    {
        "diagnosis": "Hyperlipidemia",
        "icd10": "E78.5",
        "complaint": "Cholesterol follow-up",
        "specialties": ["Cardiology", "Internal Medicine", "Family Medicine"],
        "subjective": "Follow-up for elevated cholesterol on recent labs. No chest pain. Diet could be better.",
        "objective": "BP 126/80, pulse 74. Heart and lung exams normal. BMI 28.",
        "plan": "Dietary changes and exercise. Consider statin therapy. Repeat lipid panel in 3 months.",
    },
    {
        "diagnosis": "Chronic Kidney Disease, stage 3",
        "icd10": "N18.30",
        "complaint": "Kidney function follow-up",
        "specialties": ["Nephrology", "Internal Medicine", "Family Medicine"],
        "subjective": "Follow-up for chronic kidney disease. Reports mild fatigue and ankle swelling. Blood pressure controlled on current medication. Limits salt intake.",
        "objective": "BP 138/82, pulse 78. Trace bilateral ankle edema. Lungs clear. eGFR 48 mL/min on recent labs.",
        "plan": "Continue ACE inhibitor. Low-sodium, kidney-friendly diet. Avoid NSAIDs. Repeat renal panel and urine albumin in 3 months. Nephrology follow-up.",
    },
]


def _condition(diagnosis: str) -> dict:
    return next(c for c in CONDITIONS if c["diagnosis"] == diagnosis)


def _sentence_case_list(items: list[str]) -> str:
    return ", ".join(items)


def _seed_doctors(fake: Faker) -> list[scheduling.Doctor]:
    doctors = []
    with scheduling.get_session() as session:
        for i, specialty in enumerate(DOCTOR_SPECIALTIES, start=1):
            doctor = scheduling.Doctor(
                doctor_id=f"D{i:03d}",
                name=f"Dr. {fake.first_name()} {fake.unique.last_name()}",
                specialty=specialty,
            )
            session.add(doctor)
            doctors.append(doctor)
    return doctors


def _seed_patients(fake: Faker, doctors: list[scheduling.Doctor]) -> list[records.Patient]:
    today = date.today()
    patients = []
    encounter_number = 0
    with records.get_session() as session:
        for i in range(1, NUM_PATIENTS + 2):
            if i == NUM_PATIENTS + 1:
                # Fixed sample patient: a 70-year-old man with chronic kidney disease.
                gender, first, last, age = "Male", "Harold", "Whitfield", 70
                history = [
                    _condition("Chronic Kidney Disease, stage 3"),
                    _condition("Essential Hypertension"),
                ]
            else:
                gender = random.choice(["Female", "Male"])
                first = fake.first_name_female() if gender == "Female" else fake.first_name_male()
                last = fake.last_name()
                age = random.randint(18, 85)
                history = random.sample(CONDITIONS, k=random.choice([0, 1, 1, 2, 3]))
            dob = today - timedelta(days=age * 365 + random.randint(0, 364))
            visit_dates = sorted(
                today - timedelta(days=random.randint(14, 3 * 365)) for _ in history
            )
            diagnoses = []
            for condition, visit_date in zip(history, visit_dates):
                encounter_number += 1
                provider = random.choice(
                    [d for d in doctors if d.specialty in condition["specialties"]]
                )
                session.add(
                    records.Encounter(
                        encounter_id=f"E{encounter_number:04d}",
                        patient_id=f"P{i:04d}",
                        visit_date=visit_date,
                        provider=provider.name,
                        chief_complaint=condition["complaint"],
                        subjective=condition["subjective"],
                        objective=condition["objective"],
                        assessment=f"Diagnosis: {condition['diagnosis']} ({condition['icd10']})",
                        plan=condition["plan"],
                        diagnosis=condition["diagnosis"],
                        icd10_code=condition["icd10"],
                    )
                )
                diagnoses.append(condition["diagnosis"])

            patient = records.Patient(
                patient_id=f"P{i:04d}",
                name=f"{first} {last}",
                dob=dob,
                gender=gender,
                phone=fake.numerify("###-###-####"),
                email=f"{first}.{last}@example.com".lower(),
                address=f"{fake.street_address()}, {fake.city()}, {fake.state_abbr()}",
                summary=(
                    f"History of {_sentence_case_list(diagnoses)}."
                    if diagnoses
                    else "No prior visits on file."
                ),
            )
            session.add(patient)
            patients.append(patient)
    return patients


def _seed_appointments(
    patients: list[records.Patient], doctors: list[scheduling.Doctor]
) -> int:
    """Book upcoming visits, mostly in the next week so doctors' earliest
    openings differ."""
    now = datetime.now()
    booked = 0
    with scheduling.get_session() as session:
        for patient in patients:
            for _ in range(random.choice([0, 0, 1, 1, 2][: MAX_UPCOMING_PER_PATIENT + 3])):
                doctor = random.choice(doctors)
                horizon = random.choice([5, 5, 14])
                slots = open_slots(
                    session, doctor.doctor_id, now, now + timedelta(days=horizon)
                )
                if not slots:
                    continue
                session.add(
                    scheduling.Appointment(
                        doctor_name=doctor.name,
                        doctor_id=doctor.doctor_id,
                        patient_id=patient.patient_id,
                        date=random.choice(slots),
                    )
                )
                session.flush()
                booked += 1
    return booked


def seed() -> None:
    random.seed(SEED)
    fake = Faker()
    Faker.seed(SEED)

    records.reset_records_db()
    scheduling.reset_scheduling_db()

    doctors = _seed_doctors(fake)
    patients = _seed_patients(fake, doctors)
    booked = _seed_appointments(patients, doctors)

    print(
        f"Seeded {len(doctors)} doctors, {len(patients)} patients, "
        f"and {booked} upcoming appointments."
    )


if __name__ == "__main__":
    seed()
