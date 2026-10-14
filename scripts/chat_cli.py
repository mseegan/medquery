"""Chat with the MedQuery flow in the terminal. Run from the repo root:
python scripts/chat_cli.py   (type 'quit' to exit)"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.orchestrator.flow import chat_turn  # noqa: E402

GREETING = (
    "Hi, I'm the MedQuery assistant. I'll look up your history, learn about your concern, "
    "match you with the right doctor, and book a time. To start, what's your first and last name?"
)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    thread_id = str(uuid.uuid4())
    print(f"MedQuery: {GREETING}\n")
    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if message.lower() in {"quit", "exit"}:
            break
        if not message:
            continue
        turn = chat_turn(thread_id, message)
        print(f"\nMedQuery [{', '.join(turn.agents)}]: {turn.reply}\n")


if __name__ == "__main__":
    main()
