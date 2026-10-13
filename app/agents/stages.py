from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from app.agents.prompts import (
    CANCELLATION_RULE,
    INTAKE_PROMPT,
    ROUTE_PROMPT,
    SCHEDULE_PROMPT,
    TRIAGE_PROMPT,
    make_prompt,
)
from app.config import settings
from app.orchestrator.state import FlowState
from app.tools.appointment_tools import (
    confirm_booking,
    confirm_cancellation,
    find_doctors_with_availability,
    get_availability,
    get_patient_records,
    identify_patient,
    propose_booking,
    propose_cancellation,
    recommend_specialty,
    select_doctor,
)
from app.tools.medlineplus_tools import medlineplus_search
from app.tools.who_tools import who_fact_sheet_search, who_gho_lookup


CANCELLATION_TOOLS = [get_patient_records, propose_cancellation, confirm_cancellation]


def _stage_agent(
    name: str, model_name: str, tools: list, prompt: str, can_cancel: bool = True
):
    return create_react_agent(
        model=ChatAnthropic(model=model_name, api_key=settings.anthropic_api_key),
        tools=tools + (CANCELLATION_TOOLS if can_cancel else []),
        prompt=make_prompt(prompt, CANCELLATION_RULE if can_cancel else ""),
        name=name,
        state_schema=FlowState,
    )


def build_intake_agent():
    return _stage_agent(
        "intake_agent",
        settings.haiku_model,
        [identify_patient, get_patient_records],
        INTAKE_PROMPT,
        can_cancel=False,
    )


def build_triage_agent():
    return _stage_agent(
        "triage_agent",
        settings.sonnet_model,
        [medlineplus_search, who_fact_sheet_search, who_gho_lookup, recommend_specialty],
        TRIAGE_PROMPT,
    )


def build_route_agent():
    return _stage_agent(
        "route_agent",
        settings.haiku_model,
        [find_doctors_with_availability, select_doctor],
        ROUTE_PROMPT,
    )


def build_schedule_agent():
    return _stage_agent(
        "schedule_agent",
        settings.haiku_model,
        [get_availability, propose_booking, confirm_booking, select_doctor],
        SCHEDULE_PROMPT,
    )
