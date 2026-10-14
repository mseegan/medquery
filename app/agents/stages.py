from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from app.agents.prompts import (
    HISTORY_PROMPT,
    ISSUE_PROMPT,
    BOOKING_PROMPT,
    make_prompt,
)
from app.config import settings
from app.orchestrator.state import FlowState
from app.tools.history_tools import add_history_entry, update_patient_profile
from app.tools.issue_tools import recommend_specialty
from app.tools.patient_tools import get_patient_history, identify_patient
from app.tools.research_tools import research_disease
from app.tools.routing_tools import find_doctors, select_doctor
from app.tools.scheduling_tools import confirm_booking, get_availability, propose_booking


def _stage_agent(name: str, model_name: str, tools: list, prompt: str):
    return create_react_agent(
        model=ChatAnthropic(model=model_name, api_key=settings.anthropic_api_key),
        tools=tools,
        prompt=make_prompt(prompt),
        name=name,
        state_schema=FlowState,
    )


def build_history_agent():
    return _stage_agent(
        "history_agent",
        settings.haiku_model,
        [identify_patient, get_patient_history, add_history_entry, update_patient_profile],
        HISTORY_PROMPT,
    )


def build_issue_agent():
    return _stage_agent(
        "issue_agent",
        settings.sonnet_model,
        [research_disease, recommend_specialty],
        ISSUE_PROMPT,
    )


def build_booking_agent():
    return _stage_agent(
        "booking_agent",
        settings.haiku_model,
        [recommend_specialty, find_doctors, select_doctor, get_availability, propose_booking, confirm_booking],
        BOOKING_PROMPT,
    )
