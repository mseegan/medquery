# MedQuery

MedQuery is a multi-agent LLM application for a medical context, built with LangChain / LangGraph
and Claude. **This is a demo application, not a production system** — see Limitations below.

There's no login and no doctor-facing chat — this is a single, patient-facing chat. Two
specialist agents sit behind a supervisor that decides what a message needs:

- **appointment_agent** — checks availability and books/cancels/reviews the patient's own
  appointments against a local, synthetic (Faker-generated) SQLite database. It doesn't know who
  it's talking to up front: the first time it needs a `patient_id` in a conversation, it asks for
  the user's first and last name and resolves that to a patient record with the
  `identify_patient` tool — matching an existing synthetic patient by name, or creating a new one
  on the spot if there's no match. It reuses that identity for the rest of the conversation.
- **reference_agent** — looks up general health/disease reference information from MedlinePlus
  (via its documented Web Service API) and WHO (via the WHO Global Health Observatory API for
  statistics, and Claude's server-side `web_search` tool restricted to who.int for fact sheets).
  Needs no identity at all.

A single supervisor graph (`langgraph_supervisor`) routes each turn to one or both agents — e.g.
"book me with a cardiologist next week and tell me about atrial fibrillation" hits both in one
turn.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
python scripts/seed_db.py
uvicorn app.main:app --reload
```

Open http://localhost:8000 and just start chatting — no account needed. If you ask about
appointments, the assistant will ask for your name.

## Verifying it works

There is no formal test suite (see Limitations). Instead:

```bash
python scripts/demo_conversation.py
```

runs scripted conversations against the real supervisor graph and the real Anthropic API,
covering pure-appointment, pure-reference, a compound request needing both agents, and a full
propose-then-confirm booking flow (including the agent asking for a name and resolving/creating a
patient record mid-conversation). It's also useful as a ready-made transcript for a demo.

## Limitations (by design, for a demo)

- **No real patient data.** All doctors, patients, and appointments are synthetic
  (`app/db/seed.py`, via Faker). Nothing here should be pointed at real PHI.
- **No authentication at all.** Identity is just "whatever name the user typed in chat" —
  `identify_patient` matches by name only, with no password or verification of any kind. Anyone
  can claim any name (including one that happens to match an existing synthetic patient) and the
  agent will treat them as that patient.
- **In-memory sessions.** LangGraph's `MemorySaver` checkpointer (conversation history, and with
  it the patient identity the agent resolved) is in-process and resets whenever the server
  restarts, or when the browser tab gets a new `session_id` (a fresh random id per page load).
- **No automated test suite.** Verified via `scripts/demo_conversation.py` and manual use of the
  frontend, not `pytest`.
- **Reference agent output is informational only.** Every reply that used `reference_agent`
  carries an appended disclaimer: it is not a diagnosis or personalized medical advice.
