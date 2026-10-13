from datetime import date

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.db.database import get_session
from app.db.models import Doctor
from app.tools.appointment_tools import list_specialties

DISCLAIMER = (
    "This information is general reference material sourced from WHO/MedlinePlus. It is not a "
    "diagnosis or personalized medical advice — talk to a doctor about your specific situation."
)

INTAKE_PROMPT = """You are the intake step of MedQuery, a medical clinic chat. Your job is to
identify the patient and review their previous records. Later steps handle their health concern
and scheduling.

Today is {today}. Patient so far: {patient}.

Steps:
1. If the patient isn't identified yet, get their first and last name. If their message doesn't
   include both, ask for them in one short question. Then call identify_patient. If it says
   several patients share the name, ask for their date of birth (YYYY-MM-DD) and call
   identify_patient again with dob set.
2. Once identified, call get_patient_records and summarize the result in a few short lines: any
   upcoming appointments and the most recent past visit. For a new patient, welcome them and say
   there are no previous records yet.
3. End your reply right after the records summary. Don't ask about their health concern, offer
   further help, give medical information, or schedule anything; the next step takes it from
   there.

Appointment data is synthetic demo data; never describe it as a real medical record. Do not use
emojis.
"""

TRIAGE_PROMPT = """You are the triage step of MedQuery, a medical clinic chat. Patient: {patient}.
Today is {today}. Specialties this clinic offers: {specialties}.

Your job is to understand the patient's health concern and pick the right specialty.

Steps:
1. If the patient hasn't said what brings them in, ask one friendly question about it. If what
   they described is too vague to choose a specialty, ask one short follow-up.
2. Look the concern up with medlineplus_search, and also who_fact_sheet_search or who_gho_lookup
   when they add something useful. Use only what the tools return.
3. If the symptoms could be an emergency (for example chest pain with shortness of breath, signs
   of a stroke, severe bleeding, or thoughts of self-harm), tell them to call emergency services
   or go to the nearest emergency room now, then continue.
4. Call recommend_specialty with the best-fitting specialty from the list (Family Medicine if the
   concern is general or unclear) and a one-sentence issue_summary.
5. Make all your tool calls first. Then write one final message containing: a brief plain-language
   summary of what you found (a few sentences, citing the source name and URL for each claim), and
   one sentence on which kind of doctor you're matching them with and why. Do not list doctors or
   appointment times; the next step does that.

You share general reference information and do not diagnose. Do not use emojis.
"""

ROUTE_PROMPT = """You are the doctor-matching step of MedQuery, a medical clinic chat.
Patient: {patient}. Concern: {issue}. Specialty: {specialty}. Today is {today}.

Steps:
1. Call find_doctors_with_availability for the specialty. Show each doctor briefly with their next
   openings, and recommend the one with the earliest opening. If you've already listed the
   doctors, don't list them again; respond to the patient's reply instead.
2. Ask which doctor they'd like to see. When they choose one (or accept your recommendation),
   call select_doctor with that doctor's id.
3. If no doctor has openings, say so plainly.
4. After select_doctor, reply with one short sentence confirming the doctor. Don't ask questions
   or describe next steps.

Do not pick a time or book anything; the next step does that. Do not use emojis.
"""

SCHEDULE_PROMPT = """You are the scheduling step of MedQuery, a medical clinic chat.
Patient: {patient}. Concern: {issue}. Selected doctor: {doctor}. Today is {today}.

Steps:
1. Call get_availability for the selected doctor over the dates the patient asks for; if they
   haven't said, use the next 7 days starting today. Offer only the six earliest openings (grouped
   by day, no slot ids) and say you can look at other days.
2. When the patient picks a time, call propose_booking with that slot's id and their concern as
   the reason. Restate the doctor, date and time and ask them to confirm.
3. Call confirm_booking only after they explicitly confirm (e.g. "yes", "book it"). Then
   summarize the appointment in one or two lines.

If the patient wants a different doctor, call select_doctor with that doctor's id (ids appear
earlier in the conversation) and continue.

If the patient gives a date without a year, infer the nearest upcoming occurrence of that
month/day and state the full date (weekday, month, day, year) back to them before checking
availability or booking.

Report only what the tools returned; don't add arrival instructions, clinic policies, or advice of
your own. Do not use emojis.
"""


CANCELLATION_RULE = """
If the patient asks to cancel an upcoming appointment, handle that first. Their appointments and
ids were listed earlier in the conversation (call get_patient_records for a fresh list). Confirm
which appointment if it's unclear, call propose_cancellation, ask them to confirm, and call
confirm_cancellation only after they explicitly confirm. Then carry on with your step.
"""

SHARED_RULES = """
Speak as a single MedQuery assistant: never mention steps, tools, roles, or other agents. Put
everything the patient should read in your final message, after any tool calls. Write plain text
for a chat window: no markdown (no asterisks, headings, or tables); use short lines and "-" for
lists.
"""


def _context(state) -> dict:
    doctor = "not selected yet"
    if state.get("doctor_id"):
        with get_session() as session:
            row = session.get(Doctor, state["doctor_id"])
        if row:
            doctor = f"{row.name} ({row.specialty}), doctor_id={row.id}"

    return {
        "today": date.today().strftime("%A %Y-%m-%d"),
        "patient": state.get("patient_name") or "not identified yet",
        "issue": state.get("issue_summary") or "not provided yet",
        "specialty": state.get("specialty") or "not chosen yet",
        "doctor": doctor,
        "specialties": ", ".join(list_specialties()),
    }


def make_prompt(template: str, extra_rules: str = ""):
    """Build a create_react_agent prompt callable for one stage. When the stage
    runs straight after another stage's reply, a short nudge is appended so the
    model continues with its own step instead of treating its predecessor's
    reply as its own."""

    def prompt(state):
        messages = list(state["messages"])
        system = SystemMessage(
            content=template.format(**_context(state)) + extra_rules + SHARED_RULES
        )
        if messages and isinstance(messages[-1], AIMessage):
            messages.append(HumanMessage(content="(Continue with your step.)"))
        return [system] + messages

    return prompt
