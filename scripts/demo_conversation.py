"""Scripted end-to-end conversations against the real supervisor graphs and
the real Anthropic API. Run from the repo root: python scripts/demo_conversation.py

This doubles as the verification pass (see the plan's Verification Plan) and
as a ready-made transcript for a demo. No server or frontend needs to be
running.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.seed import seed  # noqa: E402
from app.orchestrator.supervisor import supervisors  # noqa: E402


def run_turn(graph, thread_id: str, message: str) -> str:
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke({"messages": [{"role": "user", "content": message}]}, config=config)
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

    patient_graph = supervisors.for_role("patient")
    doctor_graph = supervisors.for_role("doctor")

    section("PATIENT — pure appointment availability")
    run_turn(
        patient_graph,
        "demo-patient-availability",
        "What doctors do you have, and can you show me open slots with a "
        "pediatrician in the next week?",
    )

    section("PATIENT — propose -> confirm booking flow")
    thread = "demo-patient-booking"
    run_turn(
        patient_graph,
        thread,
        "I'm patient P001. Please book me the earliest available slot with "
        "any Family Medicine doctor in the next week.",
    )
    run_turn(patient_graph, thread, "Yes, please confirm that booking.")

    section("PATIENT — guardrail: reference_agent must not be reachable")
    run_turn(
        patient_graph,
        "demo-patient-guardrail",
        "Can you pull up the WHO fact sheet on tuberculosis for me?",
    )

    section("DOCTOR — pure medical reference lookup")
    run_turn(
        doctor_graph,
        "demo-doctor-reference",
        "What does MedlinePlus say about managing type 2 diabetes?",
    )

    section("DOCTOR — compound request needing both agents")
    run_turn(
        doctor_graph,
        "demo-doctor-compound",
        "Show me open appointment slots for any cardiologist in the next 3 "
        "days, and also pull WHO guidance on tuberculosis treatment.",
    )


if __name__ == "__main__":
    main()
