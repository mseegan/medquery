from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

# Injected from flow state, so the model never supplies (or can alter) these.
PatientIdFromState = Annotated[str | None, InjectedState("patient_id")]
DoctorIdFromState = Annotated[str | None, InjectedState("doctor_id")]
ProposedSlotFromState = Annotated[str | None, InjectedState("proposed_slot")]
ToolCallId = Annotated[str, InjectedToolCallId]

NOT_IDENTIFIED = "Error: the patient hasn't been identified yet."
NO_DOCTOR = "Error: no doctor has been selected yet."


def commit(tool_call_id: str, content: str, **state_updates) -> Command:
    """Tool result that also records values in the flow state."""
    return Command(
        update={
            **state_updates,
            "messages": [ToolMessage(content=content, tool_call_id=tool_call_id)],
        }
    )
