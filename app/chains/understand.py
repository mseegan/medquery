"""Summarize chain: turns the patient's latest message (plus recent conversation
and long-term memory) into a structured RequestSummary."""
from functools import lru_cache

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

from app.chains.schemas import RequestSummary
from app.config import settings
from app.memory.service import patient_context
from app.tools.issue_tools import list_specialties

RECENT_MESSAGES = 4

UNDERSTAND_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You read a message sent to a medical clinic's chat assistant and restate it as a "
            "structured request. Rules:\n"
            "- The person chatting may be asking for someone else. Set patient.relationship to "
            "who the patient is to them (for example 'My 70-year-old father...' means father, "
            "age 70). Use 'self' when they speak about themselves.\n"
            "- Extract only what is stated. Never invent names, ages, diagnoses, or medications.\n"
            "- actions: update_history when they report a diagnosis, medication, or past event "
            "worth saving; research when they want information about a condition or its "
            "treatment; book_appointment when they want to see a doctor. A described health "
            "concern with no other request implies research and book_appointment. If the message "
            "is only a greeting, thanks, or an answer to a question the assistant just asked "
            "(such as giving a name), actions is empty.\n"
            "- research: when research is an action, name the condition to look up (or, if only "
            "symptoms were described, the most likely condition) and one focus keyword.\n"
            "- specialty: the best match from the clinic's specialty list, written exactly as "
            "listed ('a nephrologist' means Nephrology). Use General Practice for a general or "
            "unclear health concern. Null if there is no concern or request for a doctor.\n"
            "- urgency: emergency for things like chest pain with trouble breathing, stroke "
            "signs, severe bleeding, or thoughts of self-harm; urgent for symptoms that should "
            "be seen within a day or two; otherwise routine.",
        ),
        (
            "human",
            "Clinic specialties: {specialties}\n\n"
            "Patient on file for this chat: {patient}\n\n"
            "{memory}\n\n"
            "Recent conversation:\n{recent}\n\n"
            "Latest message:\n{message}",
        ),
    ]
)


@lru_cache
def _structured_model():
    model = ChatAnthropic(model=settings.sonnet_model, api_key=settings.anthropic_api_key)
    return model.with_structured_output(RequestSummary)


def _recent(messages) -> str:
    lines = []
    for message in messages:
        if message.type in {"human", "ai"} and not getattr(message, "tool_calls", None):
            text = message.content if isinstance(message.content, str) else ""
            if text.strip():
                speaker = "Patient" if message.type == "human" else "Assistant"
                lines.append(f"{speaker}: {text.strip()[:400]}")
    return "\n".join(lines[-RECENT_MESSAGES:]) or "none"


def summarize_request(
    message: str,
    prior_messages=(),
    patient_id: str | None = None,
    patient_name: str | None = None,
) -> RequestSummary:
    chain = UNDERSTAND_PROMPT | _structured_model()
    return chain.invoke(
        {
            "specialties": ", ".join(list_specialties()),
            "patient": patient_name or "not identified yet",
            "memory": patient_context(patient_id, message),
            "recent": _recent(prior_messages),
            "message": message,
        }
    )
