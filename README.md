# MedQuery

MedQuery is a multi-agent chat backend that gets a patient from first hello to a booked appointment
with the right doctor. It's built with LangChain / LangGraph and Claude.

## Chat flow

Four agents hand the conversation to each other in order (`app/orchestrator/flow.py`):

1. **History** — asks for the patient's first and last name, finds their record (or creates one),
   and summarizes known conditions, recent visits, and upcoming appointments.
2. **Issue** — asks what brings them in, looks the concern up in MedlinePlus and WHO (with source
   links), considers the patient's history, and picks a specialty. Urgent symptoms get an emergency
   caution.
3. **Routing** — lists the doctors in that specialty with their next openings and records the
   patient's choice.
4. **Scheduling** — checks the chosen doctor's availability for the dates the patient asks about,
   holds a time, and books it after the patient confirms.

When one stage finishes, the next picks up in the same turn, so the patient sees one combined
reply. After a booking, the next message starts a new request for the same patient.

## Databases

Two SQLite databases, created under `data/` (`app/db/`):

**`records.db`** (patient records)

| Table | Columns |
|---|---|
| `patients` | `patient_id`, `name`, `dob`, `gender`, `phone`, `email`, `address`, `summary` |
| `encounters` | `encounter_id`, `patient_id`, `visit_date`, `provider`, `chief_complaint`, `subjective`, `objective`, `assessment`, `plan`, `diagnosis`, `icd10_code` |

**`scheduling.db`** (doctors and bookings)

| Table | Columns |
|---|---|
| `doctors` | `doctor_id`, `name`, `specialty` |
| `appointments` | `appointment_id`, `doctor_name`, `doctor_id`, `patient_id`, `date` |

`appointments` holds booked rows only. A doctor's open times are the clinic's working hours (Mon-Fri,
30-minute slots, 9-12 and 1-5) minus that doctor's booked rows (`app/db/availability.py`), and
`(doctor_id, date)` is unique so a time can't be booked twice.

`scripts/seed_db.py` fills both databases with synthetic data: 13 doctors across 12 specialties,
40 patients with SOAP-style visit notes and ICD-10 diagnoses, and a set of upcoming appointments.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
python scripts/seed_db.py
```

## Try it

```bash
python scripts/chat_cli.py          # chat in the terminal
python scripts/demo_conversation.py # scripted run through the whole flow
```

## Layout

- `app/db/` — the two databases, availability logic, and seed data
- `app/tools/` — agent tools: patient lookup, MedlinePlus/WHO lookup, routing, scheduling
- `app/agents/` — one agent and prompt per stage
- `app/orchestrator/` — flow state and the LangGraph that connects the stages
