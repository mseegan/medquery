# MedQuery

MedQuery is a multi-agent chat backend that helps a patient, or a family member acting for them,
get from a request like this to a booked appointment:

> "My 70-year-old father has chronic kidney disease. I want to book a nephrologist for him. Also,
> can you summarize latest treatment methods?"

It is built with LangChain / LangGraph and Claude. A message is summarized, planned, acted on by
specialist agents, and answered in one reply.

## How a message is handled

1. **Summarize** (`app/chains/understand.py`) — a chain reads the message, recent chat, and the
   patient's long-term memory and returns a structured request: who the patient is (the person
   chatting, or a father, mother, spouse...), their conditions and symptoms, what they want
   (update history, research, book), the condition to research, the specialty, and urgency.
2. **Plan** (`app/chains/plan.py`) — a chain writes a goal for each step, and code enforces the
   order: identify the patient first, then research, and booking last since it needs the patient's
   replies. Only the steps the request calls for are included.
3. **Act** (`app/orchestrator/`) — a LangGraph runs the steps:
   - **History agent** — finds or creates the patient's record, reads their history, and records
     reported diagnoses and profile changes.
   - **Disease-research tool** — looks up MedlinePlus, PubMed reviews from the last three years,
     and WHO guidance in parallel, and a chain writes a summary with numbered citations.
   - **Booking agent** — picks the specialty if needed, lists that specialty's doctors with their
     next openings, checks availability, holds a time, and books it once the patient confirms.
4. **Compose** (`app/chains/compose.py`) — a chain merges what the steps produced into one reply.
   The research text and its citations are inserted as written, and urgent requests get emergency
   advice first.

Plan progress is saved with the conversation, so a step that needs the patient's reply (for
example "what is your father's name?") picks up on the next message. A request about someone else
gets that person's own record, and after a booking the next message starts a new request for the
same patient.

## Memory

- **Vector store** (`app/memory/`) — a persistent Chroma collection with local embeddings. It
  holds each patient's generated summary, text imported from the records spreadsheet, and notes
  remembered from conversations (caregiver relationship, research asked for, bookings). Every
  search is filtered to one patient.
- **Summary chain** — turns a patient's chart into a short summary, and runs again whenever the
  history agent records something.
- **In prompts** — each agent's prompt includes the identified patient's summary and the notes
  most relevant to their latest message.
- **Conversations** — saved in SQLite (`data/checkpoints.db`), so they continue after a restart.

## Databases

Two SQLite databases, created under `data/` (`app/db/`):

**`records.db`** (patient records)

| Table | Columns |
|---|---|
| `patients` | `patient_id`, `name`, `dob`, `age`, `mrn`, `gender`, `phone`, `email`, `address`, `summary` |
| `encounters` | `encounter_id`, `patient_id`, `visit_date`, `provider`, `chief_complaint`, `subjective`, `objective`, `assessment`, `plan`, `diagnosis`, `icd10_code` |

**`scheduling.db`** (doctors and bookings)

| Table | Columns |
|---|---|
| `doctors` | `doctor_id`, `name`, `specialty` |
| `appointments` | `appointment_id`, `doctor_name`, `doctor_id`, `patient_id`, `date` |

`appointments` holds booked rows only. A doctor's open times are the clinic's working hours (Mon-Fri,
30-minute slots, 9-12 and 1-5) minus that doctor's booked rows (`app/db/availability.py`), and
`(doctor_id, date)` is unique so a time can't be booked twice.

`scripts/seed_db.py` fills everything from fixed inputs:

- **Doctors** come from `seed_data/doctors.json`: 16 doctors, one per specialty across 14 specialties
  plus 2 general practitioners. Edit that file to change the roster.
- **Patients** come from `records.xlsx` in your records folder (repeated rows are merged).
- **Visit notes** are parsed from the PDFs in the same folder into SOAP sections, diagnoses, and
  ICD-10 codes, and attached to the matching patient.
- **Memory** is rebuilt from those records, with a generated summary for each patient.
- **Appointments** start empty; the chat creates them.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY and RECORDS_DATA_DIR
python scripts/seed_db.py
```

The embedding model (about 80 MB) downloads the first time memory is built. Use
`python scripts/seed_db.py --no-memory` to seed the databases without calling the API.

## Try it

```bash
python scripts/chat_cli.py           # chat in the terminal
python scripts/demo_conversation.py  # scripted run through a full booking
python scripts/verify_e2e.py         # end-to-end checks against the live services
```

`verify_e2e.py` reseeds everything, then runs scripted conversations (a returning patient, the
father example followed by a request for a different patient, an emergency, and an
information-only question) and checks the replies, saved state, databases, and memory.

## Layout

- `app/chains/` — the summarize, plan, and compose chains and their structured output schemas
- `app/orchestrator/` — flow state, the LangGraph executor, and its nodes
- `app/agents/` — the history and booking agents and their prompts
- `app/tools/` — agent tools: patient lookup and history, specialty and doctor routing, scheduling,
  disease research
- `app/research/` — the MedlinePlus, PubMed, and WHO sources and the research chain
- `app/memory/` — the vector store, memory service, and summarization chain
- `app/db/` — the two databases, availability logic, loaders, and seeding
