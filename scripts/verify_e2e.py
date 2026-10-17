"""End-to-end verification against the real Anthropic, MedlinePlus, PubMed, and
WHO services. Run from the repo root: python scripts/verify_e2e.py

Reseeds the databases and vector store, then runs scripted conversations and
checks the replies, the saved conversation state, the databases, and the
patient memory. Exits non-zero if any check fails. Takes several minutes."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import records, scheduling  # noqa: E402
from app.db.seed import seed  # noqa: E402
from app.memory.indexing import rebuild_memory  # noqa: E402
from app.memory.service import recall  # noqa: E402
from app.orchestrator.flow import chat_turn, flow  # noqa: E402

results: list[tuple[str, bool]] = []
section = ""


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((f"{section}: {name}", bool(ok)))
    print(f"   [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not ok else ""))


def say(thread: str, message: str):
    started = time.time()
    turn = chat_turn(thread, message)
    preview = turn.reply.replace("\n", " ")[:170]
    print(f"\n   Patient: {message}\n   MedQuery {turn.agents} ({time.time() - started:.0f}s): {preview}")
    if "[[" in turn.reply:  # an internal placeholder must never reach the patient
        check("reply has no leftover placeholder", False, preview)
    return turn


def state(thread: str) -> dict:
    return flow.get_state({"configurable": {"thread_id": thread}}).values


def steps(thread: str) -> list[tuple[str, str]]:
    return [(s["agent"], s["status"]) for s in state(thread).get("plan") or []]


def appointments(patient_id: str | None = None) -> list:
    with scheduling.get_session() as session:
        query = session.query(scheduling.Appointment)
        if patient_id:
            query = query.filter(scheduling.Appointment.patient_id == patient_id)
        return query.order_by(scheduling.Appointment.appointment_id).all()


def specialty_of(doctor_id: str) -> str:
    with scheduling.get_session() as session:
        return session.get(scheduling.Doctor, doctor_id).specialty


def patient_named(name: str):
    with records.get_session() as session:
        return session.query(records.Patient).filter(records.Patient.name.ilike(name)).first()


def returning_patient() -> None:
    """A seeded patient describes symptoms, books, then makes a second request."""
    global section
    section = "Returning patient (David Thompson)"
    print(f"\n=== {section} ===")
    thread = "e2e-david"

    turn = say(thread, "Hi, I'm David Thompson. I've been extremely thirsty lately and I'm "
                       "urinating a lot more than usual.")
    s = state(thread)
    check("identified the existing record without creating a duplicate", s["patient_id"] == "P0005")
    check("ran history, research, and booking agents",
          {"history_agent", "research_tool", "booking_agent"} <= set(turn.agents), str(turn.agents))
    check("research was cited", turn.used_reference and "Sources" in turn.reply)
    check("chose Endocrinology and offered its doctor", s["specialty"] == "Endocrinology" and "Iyer" in turn.reply)
    check("history and research done, booking waiting on the patient",
          steps(thread) == [("history", "done"), ("research", "done"), ("booking", "pending")], str(steps(thread)))

    say(thread, "The first doctor you listed sounds good.")
    check("doctor selected", state(thread)["doctor_id"] == "D006")
    say(thread, "Whatever the earliest opening is works for me.")
    check("a time is on hold", bool(state(thread)["proposed_slot"]))
    say(thread, "Yes, please book it.")
    booked = appointments("P0005")
    check("appointment saved for the patient", len(booked) == 1 and booked[0].doctor_id == "D006")
    check("saved row has doctor name, doctor id, patient id, and date",
          bool(booked) and all([booked[0].doctor_name, booked[0].doctor_id, booked[0].patient_id, booked[0].date]))
    check("plan complete", all(status == "done" for _, status in steps(thread)))

    turn = say(thread, "Can I also book a cardiologist for myself?")
    check("second request skipped identification and research",
          turn.agents == ["booking_agent"], str(turn.agents))
    check("same patient, new specialty",
          state(thread)["patient_id"] == "P0005" and state(thread)["specialty"] == "Cardiology")
    say(thread, "Dr. Rossi sounds good.")
    say(thread, "The earliest one.")
    say(thread, "Yes, book it.")
    booked = appointments("P0005")
    check("second appointment is with a cardiologist",
          len(booked) == 2 and specialty_of(booked[1].doctor_id) == "Cardiology")


def father_then_mother() -> None:
    """The example request, then a request for a different person in the same chat."""
    global section
    section = "Father example, then a different patient"
    print(f"\n=== {section} ===")
    thread = "e2e-father"

    turn = say(thread, "My 70-year-old father has chronic kidney disease. I want to book a "
                       "nephrologist for him. Also, can you summarize latest treatment methods?")
    check("asked for the father's name before anything else", turn.agents == ["history_agent"], str(turn.agents))
    check("planned history, research, and booking",
          steps(thread) == [("history", "pending"), ("research", "pending"), ("booking", "pending")])
    check("recorded that the patient is the requester's father", state(thread)["patient_relationship"] == "father")

    turn = say(thread, "His name is Robert Hale, born April 2, 1956.")
    s = state(thread)
    robert = patient_named("Robert Hale")
    check("created a record for the father", robert is not None and str(robert.dob) == "1956-04-02")
    check("recorded the kidney disease in his history", robert is not None and any(
        "kidney" in e.diagnosis.lower() for e in _encounters(robert.patient_id)))
    check("summarized latest treatments with citations",
          turn.used_reference and "Sources" in turn.reply and "[1]" in turn.reply)
    check("offered the nephrologist", "Zhou" in turn.reply)
    check("speaks about the father in the third person",
          "your chronic kidney" not in turn.reply.lower() and "your diagnosis" not in turn.reply.lower())

    say(thread, "Dr. Zhou sounds good.")
    say(thread, "The earliest one please.")
    say(thread, "Yes, book it.")
    booked = appointments(robert.patient_id) if robert else []
    check("booked a nephrologist under the father's record",
          len(booked) == 1 and specialty_of(booked[0].doctor_id) == "Nephrology")
    check("nothing booked for anyone else", len(appointments()) == len(booked) + _prior_bookings())

    notes = [d.page_content for d in recall(robert.patient_id, "family member booked researched", k=8, kinds=["memory"])]
    check("memory notes saved (caregiver, research, booking)",
          any("family member" in n for n in notes) and any("Booked" in n for n in notes)
          and any("asked about" in n for n in notes), str(notes))
    leaked = [d for d in recall("P0005", "chronic kidney disease Robert Hale", k=8) if "Robert" in d.page_content]
    check("father's notes never surface for another patient", not leaked)

    before = len(appointments())
    turn = say(thread, "Now I'd also like to book my mother with a dermatologist.")
    s = state(thread)
    check("switched to a new patient instead of reusing the father's",
          s["patient_id"] is None and s["patient_relationship"] == "mother", str((s["patient_id"], s["patient_relationship"])))
    check("asked for the mother's name", turn.agents == ["history_agent"] and not appointments()[before:])

    say(thread, "Her name is Linda Park.")
    s = state(thread)
    linda = patient_named("Linda Park")
    check("created a separate record for the mother", linda is not None and linda.patient_id != robert.patient_id)
    check("moved on to Dermatology booking", s["specialty"] == "Dermatology" and s["patient_name"] == "Linda Park")
    reply = state(thread)["messages"][-1].content.lower()
    check("refers to the mother as her, not 'you'", "book you" not in reply and "your concern" not in reply, reply[:120])


def _encounters(patient_id: str) -> list:
    with records.get_session() as session:
        return session.query(records.Encounter).filter(records.Encounter.patient_id == patient_id).all()


def _prior_bookings() -> int:
    return len(appointments("P0005"))


def emergency() -> None:
    global section
    section = "Emergency"
    print(f"\n=== {section} ===")
    thread = "e2e-emergency"
    turn = say(thread, "My husband is having crushing chest pain and he can't breathe.")
    check("opens with emergency advice", turn.reply.lower().startswith("if this is an emergency"))
    check("request marked emergency", (state(thread).get("request") or {}).get("urgency") == "emergency")
    check("still asks who the patient is", "history_agent" in turn.agents)
    turn = say(thread, "His name is Gregory Stone.")
    check("emergency advice is not repeated on later turns", "if this is an emergency" not in turn.reply.lower())


def info_only() -> None:
    global section
    section = "Information only"
    print(f"\n=== {section} ===")
    thread = "e2e-info"
    turn = say(thread, "I'm Ramesh Kulkarni. What are the current treatment options for hypertension?")
    check("identified the existing patient", state(thread)["patient_id"] == "P0003")
    check("researched with citations", turn.used_reference and "Sources" in turn.reply)
    check("no booking agent and no appointment", "booking_agent" not in turn.agents and not appointments("P0003"))
    check("plan finished", all(status == "done" for _, status in steps(thread)), str(steps(thread)))
    turn = say(thread, "Thanks, that's all I needed!")
    check("a thank-you gets a short reply without new research", not turn.used_reference and len(turn.reply) < 400)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print("Reseeding databases and rebuilding patient memory...")
    seed()
    rebuild_memory()

    for scenario in (returning_patient, father_then_mother, emergency, info_only):
        try:
            scenario()
        except Exception as exc:  # report and keep going so one failure doesn't hide the rest
            check(f"scenario ran without error ({type(exc).__name__}: {str(exc)[:120]})", False)

    failed = [name for name, ok in results if not ok]
    print(f"\n{'=' * 60}\n{len(results) - len(failed)}/{len(results)} checks passed")
    for name in failed:
        print(f"  FAILED: {name}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
