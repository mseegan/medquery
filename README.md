# MedQuery

MedQuery is a guided medical clinic chat for patients, built with LangChain / LangGraph and
Claude. It takes a patient from first hello to a booked appointment in one conversation:

1. **Identify** — asks for the patient's first and last name, finds their record (or creates one),
   and asks for a date of birth when several patients share a name.
2. **Records** — summarizes upcoming appointments and recent past visits from the clinic database.
3. **Triage** — asks what brings them in, looks the concern up in MedlinePlus and WHO (with source
   links), and picks the matching specialty, with an emergency caution for urgent symptoms.
4. **Route** — lists the doctors in that specialty with their next openings and recommends the
   earliest.
5. **Schedule** — shows open times for the chosen doctor, stages the booking, and confirms it once
   the patient says yes.

Patients can also cancel an upcoming appointment at any point after identifying themselves, and a
patient who has just booked can start a new request in the same chat.

## How it works

The flow is a LangGraph state machine (`app/orchestrator/flow.py`). Each stage is its own agent
with a focused prompt and toolset (`app/agents/stages.py`), and tools record their results in the
shared flow state (patient, specialty, doctor, appointment), which decides the next stage. When a
stage finishes, the next one continues in the same turn, so the patient sees one combined reply.

| Stage | Model | Tools |
|---|---|---|
| intake | Haiku | `identify_patient`, `get_patient_records` |
| triage | Sonnet | `medlineplus_search`, `who_fact_sheet_search`, `who_gho_lookup`, `recommend_specialty` |
| route | Haiku | `find_doctors_with_availability`, `select_doctor` |
| schedule | Haiku | `get_availability`, `propose_booking`, `confirm_booking`, `select_doctor` |

Triage, route, and schedule also carry the cancellation tools (`propose_cancellation`,
`confirm_cancellation`). Bookings and cancellations are staged first and applied after an explicit
confirmation. Patient identity comes from flow state, not from model-supplied arguments.

Data is synthetic: doctors, patients, recurring weekly availability, upcoming appointments, and
past visits are generated with Faker into a local SQLite database (`app/db/seed.py`).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
python scripts/seed_db.py
uvicorn app.main:app --reload
```

Open http://localhost:8000 and start chatting. Re-run `python scripts/seed_db.py` whenever you
want fresh data (it also refreshes the two weeks of open appointment slots).

## Verifying it works

```bash
python scripts/demo_conversation.py
```

walks one seeded patient through the full flow against the real Anthropic API and prints each
turn with the agents that handled it. It also serves as a ready-made demo transcript.
