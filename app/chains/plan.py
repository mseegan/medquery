"""Plan chain: turns a RequestSummary into an ordered list of steps for the
history agent, the research tool, and the booking agent."""
from functools import lru_cache

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

from app.chains.schemas import Plan, RequestSummary
from app.config import settings

# Fixed order: identify first, look things up, and finish with the interactive booking.
ORDER = ["history", "research", "booking"]

PLAN_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You plan how a medical clinic's assistant handles a patient's request. Steps run "
            "in order through these agents:\n"
            "- history: identifies the patient (finding or creating their record) and reads or "
            "updates their medical history.\n"
            "- research: looks up a condition in MedlinePlus, PubMed, and WHO and summarizes it "
            "with citations.\n"
            "- booking: chooses a doctor in the right specialty, checks availability, and books "
            "a time once the patient confirms.\n\n"
            "Rules:\n"
            "- If the patient is not identified yet, the first step is history. When the "
            "request is about someone else (a parent, child, spouse), history must identify "
            "that person, not the person chatting: ask for their full name if it isn't known.\n"
            "- Add history after the patient is identified only when there is something to "
            "record (the request includes update_history).\n"
            "- Add research only if the request includes research, and booking only if it "
            "includes book_appointment.\n"
            "- Write each goal as one specific sentence using the details from the request "
            "(conditions to record, condition to research, specialty to book).\n"
            "- If nothing needs doing and the patient is already identified, return no steps.",
        ),
        (
            "human",
            "Request summary:\n{request}\n\nPatient identified already: {identified}",
        ),
    ]
)

DEFAULT_GOALS = {
    "history": "Identify the patient and review their medical history.",
    "research": "Look up the condition and summarize it with citations.",
    "booking": "Choose a doctor, check availability, and book a time.",
}


@lru_cache
def _structured_model():
    model = ChatAnthropic(model=settings.sonnet_model, api_key=settings.anthropic_api_key)
    return model.with_structured_output(Plan)


def normalize_plan(plan: Plan, request: RequestSummary, identified: bool) -> list[dict]:
    """Enforce the plan's invariants in code, keeping the chain's goal wording:
    one step per agent, identification first when needed, booking last, and
    only the steps the request actually calls for."""
    goals = {step.agent: step.goal for step in plan.steps}

    wanted = {
        "history": (not identified) or "update_history" in request.actions,
        "research": "research" in request.actions and request.research is not None,
        "booking": "book_appointment" in request.actions,
    }
    steps = []
    for agent in ORDER:
        if not wanted[agent]:
            continue
        goal = goals.get(agent) or DEFAULT_GOALS[agent]
        if agent == "history" and not identified and "identif" not in goal.lower():
            goal = "Identify the patient first (ask for their full name if it isn't known). " + goal
        step = {"agent": agent, "goal": goal, "status": "pending"}
        if agent == "research":
            step["args"] = request.research.model_dump()
        steps.append(step)
    return steps


def plan_request(request: RequestSummary, identified: bool) -> list[dict]:
    plan = (PLAN_PROMPT | _structured_model()).invoke(
        {"request": request.model_dump_json(indent=2), "identified": "yes" if identified else "no"}
    )
    return normalize_plan(plan, request, identified)
