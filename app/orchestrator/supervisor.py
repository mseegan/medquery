from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph_supervisor import create_supervisor

from app.agents.appointment_agent import build_appointment_agent
from app.agents.reference_agent import build_reference_agent
from app.config import settings
from app.orchestrator.prompts import SUPERVISOR_SYSTEM_PROMPT


def build_supervisor():
    appointment_agent = build_appointment_agent()
    reference_agent = build_reference_agent()
    model = ChatAnthropic(model=settings.sonnet_model, api_key=settings.anthropic_api_key)
    workflow = create_supervisor(
        [appointment_agent, reference_agent],
        model=model,
        prompt=SUPERVISOR_SYSTEM_PROMPT,
        supervisor_name="supervisor",
        add_handoff_messages=True,
        output_mode="full_history",
    )
    return workflow.compile(checkpointer=MemorySaver())


supervisor = build_supervisor()
