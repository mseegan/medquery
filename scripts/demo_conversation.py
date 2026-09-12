"""Scripted end-to-end conversations against the real supervisor graph and
the real Anthropic API. Run from the repo root: python scripts/demo_conversation.py

This doubles as the verification pass (see the plan's Verification Plan) and
as a ready-made transcript for a demo. No server or frontend needs to be
running. There's no login — identity is established in-conversation via the
appointment agent's identify_patient tool, same as a real chat session.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.seed import seed  # noqa: E402
from app.orchestrator.supervisor import supervisor  # noqa: E402


def run_turn(thread_id: str, message: str) -> str:
    config = {"configurable": {"thread_id": thread_id}}
    result = supervisor.invoke({"messages": [{"role": "user", "content": message}]}, config=config)
    reply = result["messages"][-1].content
    if isinstance(reply, list):
        reply = "\n".join(block.get("text", "") for block in reply if isinstance(block, dict))
    print(f"User: {message}")
    print(f"Assistant: {reply}\n")
    return reply


def section(title: str) -> None:
    print("=" * 70)
    print(title)
    print("=" * 70)


def main() -> None:
    print("Seeding database with fresh synthetic data...\n")
    seed()

    section("Pure health reference lookup (no identity needed)")
    run_turn("demo-reference", "What does MedlinePlus say about managing type 2 diabetes?")

    section("Appointment flow — agent should ask for a name, then find/create the patient")
    thread = "demo-booking"
    run_turn(
        thread,
        "Can you show me open slots with any Family Medicine doctor in the next week?",
    )
    run_turn(thread, "My name is Jordan Rivera. Please book me the earliest one.")
    run_turn(thread, "Yes, please confirm that booking.")

    section("Compound request needing both agents")
    run_turn(
        "demo-compound",
        "My name is Jordan Rivera. Show me open appointment slots for any cardiologist "
        "in the next 3 days, and also pull WHO guidance on tuberculosis treatment.",
    )


if __name__ == "__main__":
    main()
