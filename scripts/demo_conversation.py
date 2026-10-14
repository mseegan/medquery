"""Scripted end-to-end conversation through the full MedQuery flow against the
real Anthropic API. Run from the repo root: python scripts/demo_conversation.py

Walks one seeded patient through history lookup, the health concern, doctor
routing, and booking, printing each turn and the agents that handled it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import records  # noqa: E402
from app.db.seed import seed  # noqa: E402
from app.orchestrator.flow import chat_turn  # noqa: E402

THREAD_ID = "demo-session"


def say(message: str) -> None:
    turn = chat_turn(THREAD_ID, message)
    print(f"Patient: {message}")
    print(f"MedQuery [{', '.join(turn.agents)}]:\n{turn.reply}\n")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print("Seeding databases...\n")
    seed()
    with records.get_session() as session:
        patient = (
            session.query(records.Patient)
            .join(records.Encounter, records.Encounter.patient_id == records.Patient.patient_id)
            .filter(records.Encounter.diagnosis == "Type 2 Diabetes Mellitus")
            .first()
        )

    say("Hi, I'd like to see a doctor.")
    say(f"My name is {patient.name}.")
    say("I've been extremely thirsty lately and I'm urinating a lot more than usual.")
    say("The first doctor you listed sounds good.")
    say("Whatever the earliest opening is works for me.")
    say("Yes, please book it.")


if __name__ == "__main__":
    main()
