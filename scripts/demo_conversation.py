"""Scripted conversation through the full MedQuery flow against the real
Anthropic API. Run from the repo root: python scripts/demo_conversation.py

A returning patient describes symptoms in one message. The planner looks up
their history, researches the condition, and starts the booking, and the
patient finishes it over the next few turns. Each turn prints the agents that
handled it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.seed import seed  # noqa: E402
from app.memory.indexing import rebuild_memory  # noqa: E402
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
    rebuild_memory()

    say(
        "Hi, I'm David Thompson. I've been extremely thirsty lately and I'm urinating "
        "a lot more than usual."
    )
    say("The first doctor you listed sounds good.")
    say("Whatever the earliest opening is works for me.")
    say("Yes, please book it.")


if __name__ == "__main__":
    main()
