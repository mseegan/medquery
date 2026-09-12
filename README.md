# MedQuery

MedQuery is a multi-agent LLM chat for patients, built with LangChain / LangGraph and Claude. A
supervisor graph routes each message to one or both of two specialist agents:

- **appointment_agent** — checks doctor availability and books, cancels, and reviews a patient's
  own appointments against a local, synthetic (Faker-generated) SQLite database. It resolves who
  it's talking to conversationally: the first time it needs a patient record, it asks for a first
  and last name and looks up or creates the matching patient via the `identify_patient` tool, then
  reuses that identity for the rest of the conversation.
- **reference_agent** — answers general health/disease questions using MedlinePlus (via its Web
  Service API) and WHO (via the Global Health Observatory API for statistics, and Claude's
  server-side `web_search` tool restricted to who.int for fact sheets), citing its sources.

A single request can hit both agents in one turn — e.g. "book me with a cardiologist next week
and tell me about atrial fibrillation."

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
python scripts/seed_db.py
uvicorn app.main:app --reload
```

Open http://localhost:8000 and start chatting.

## Verifying it works

```bash
python scripts/demo_conversation.py
```

runs scripted conversations against the real supervisor graph and the real Anthropic API,
covering pure-appointment, pure-reference, a compound request needing both agents, and a full
propose-then-confirm booking flow. It's also a ready-made transcript for a demo.
