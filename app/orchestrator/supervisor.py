from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph_supervisor import create_supervisor

from app.agents.appointment_agent import build_appointment_agent
from app.agents.reference_agent import build_reference_agent
from app.config import settings
from app.orchestrator.prompts import SUPERVISOR_SYSTEM_PROMPT


def _build_supervisor(agents):
    model = ChatAnthropic(model=settings.sonnet_model, temperature=0)
    workflow = create_supervisor(
        agents,
        model=model,
        prompt=SUPERVISOR_SYSTEM_PROMPT,
        supervisor_name="supervisor",
        add_handoff_messages=True,
        output_mode="full_history",
    )
    return workflow.compile(checkpointer=MemorySaver())


class Supervisors:
    """Two supervisor graphs, one per role.

    reference_agent is only ever wired into the doctor graph — it is
    structurally unreachable for a patient-role request, not just
    prompt-discouraged.
    """

    def __init__(self):
        appointment_agent = build_appointment_agent()
        reference_agent = build_reference_agent()
        self.doctor = _build_supervisor([appointment_agent, reference_agent])
        self.patient = _build_supervisor([appointment_agent])

    def for_role(self, role: str):
        return self.doctor if role == "doctor" else self.patient


supervisors = Supervisors()
