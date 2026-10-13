"""Scripted end-to-end conversation through the full MedQuery flow against the
real Anthropic API. Run from the repo root: python scripts/demo_conversation.py

Walks one patient through identification, records lookup, health-concern
triage, doctor matching, and booking, printing each turn and which agents
handled it. Doubles as the verification pass and a ready-made demo transcript.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import get_session  # noqa: E402
from app.db.models import Patient  # noqa: E402
from app.db.seed import seed  # noqa: E402
from app.orchestrator.flow import chat_turn  # noqa: E402

THREAD_ID = "demo-session"


def say(message: str) -> None:
    turn = chat_turn(THREAD_ID, message)
    print(f"Patient: {message}")
    print(f"MedQuery [{', '.join(turn.agents)}]:\n{turn.reply}\n")


def main() -> None:
    print("Seeding database with fresh synthetic data...\n")
    seed()
    with get_session() as session:
        patient_name = session.get(Patient, "P001").name

    say("Hi, I'd like to see a doctor.")
    say(f"My name is {patient_name}.")
    say("I've been having chest tightness and shortness of breath when I climb stairs.")
    say("The first doctor you listed sounds good.")
    say("Whatever the earliest opening is works for me.")
    say("Yes, please book it.")


if __name__ == "__main__":
    main()
