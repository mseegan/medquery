from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from app.agents.prompts import (
    HISTORY_PROMPT,
    ISSUE_PROMPT,
    ROUTING_PROMPT,
    SCHEDULING_PROMPT,
    make_prompt,
)
from app.config import settings
from app.orchestrator.state import FlowState
from app.tools.issue_tools import recommend_specialty
from app.tools.medlineplus_tools import medlineplus_search
from app.tools.patient_tools import get_patient_history, identify_patient
from app.tools.routing_tools import find_doctors, select_doctor
from app.tools.scheduling_tools import confirm_booking, get_availability, propose_booking
from app.tools.who_tools import who_fact_sheet_search, who_gho_lookup


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
        [identify_patient, get_patient_history],
        HISTORY_PROMPT,
    )


def build_issue_agent():
    return _stage_agent(
        "issue_agent",
        settings.sonnet_model,
        [medlineplus_search, who_fact_sheet_search, who_gho_lookup, recommend_specialty],
        ISSUE_PROMPT,
    )


def build_routing_agent():
    return _stage_agent(
        "routing_agent",
        settings.haiku_model,
        [find_doctors, select_doctor],
        ROUTING_PROMPT,
    )


def build_scheduling_agent():
    return _stage_agent(
        "scheduling_agent",
        settings.haiku_model,
        [get_availability, propose_booking, confirm_booking, select_doctor],
        SCHEDULING_PROMPT,
    )
