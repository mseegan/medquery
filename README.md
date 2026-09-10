# MedQuery

MedQuery is a multi-agent LLM application for a medical context, built with LangChain / LangGraph
and Claude. **This is a demo application, not a production system** — see Limitations below.

Two specialist agents sit behind a supervisor:

- **appointment_agent** — patients and doctors can check availability, book, and cancel
  appointments against a local, synthetic (Faker-generated) SQLite database.
- **reference_agent** — doctors only — looks up clinical reference information from MedlinePlus
  (via its documented Web Service API) and WHO (via the WHO Global Health Observatory API for
  statistics, and Claude's server-side `web_search` tool restricted to who.int for fact sheets).

A supervisor graph (`langgraph_supervisor`) routes each user turn to the right agent(s) based on
the request. Two supervisor graphs are built at startup — one for doctors (both agents) and one
for patients (appointment agent only) — so `reference_agent` is structurally unreachable from a
patient session, not just discouraged by a prompt.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
python scripts/seed_db.py
uvicorn app.main:app --reload
```

Open http://localhost:8000, pick a role (Patient/Doctor), and chat. The role selector is not real
authentication — see Limitations.

## Verifying it works

There is no formal test suite (see Limitations). Instead:

```bash
python scripts/demo_conversation.py
```

runs scripted conversations against the real supervisor graphs and the real Anthropic API,
covering pure-appointment, pure-reference, a compound doctor request needing both agents, a full
propose-then-confirm booking flow, and the patient/reference guardrail. It's also useful as a
ready-made transcript for a demo.

## Limitations (by design, for a demo)

- **No real patient data.** All doctors, patients, and appointments are synthetic
  (`app/db/seed.py`, via Faker). Nothing here should be pointed at real PHI.
- **Not authentication.** The role/user_id selected in the UI is trusted as-is — there's no login.
- **In-memory sessions.** Conversation history is held by LangGraph's `MemorySaver` checkpointer
  and resets whenever the server restarts.
- **No automated test suite.** Verified via `scripts/demo_conversation.py` and manual use of the
  frontend, not `pytest`.
- **Reference agent output is informational only.** Every reply that used `reference_agent`
  carries an appended disclaimer: it is not a diagnosis or treatment recommendation for a specific
  patient.
