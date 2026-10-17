"""Structured outputs of the summarize and plan chains."""
from typing import Literal

from pydantic import BaseModel, Field

Action = Literal["update_history", "research", "book_appointment"]
Agent = Literal["history", "research", "booking"]


class PatientRef(BaseModel):
    """The person the request is about, who may not be the person chatting."""

    relationship: str = Field(
        default="self",
        description="Who the patient is to the person chatting: self, father, mother, "
        "spouse, son, daughter, friend, and so on.",
    )
    name: str | None = Field(default=None, description="The patient's name, only if stated.")
    age: int | None = Field(default=None, description="The patient's age, only if stated.")


class ResearchTopic(BaseModel):
    disease: str = Field(
        description="The disease or condition to look up. If only symptoms were described, "
        "the most likely condition or the main symptom."
    )
    focus: str = Field(
        default="treatment",
        description="One short keyword: treatment, diagnosis, prevention, or causes.",
    )


class RequestSummary(BaseModel):
    """What the person asked for, restated in structured form."""

    patient: PatientRef
    conditions_mentioned: list[str] = Field(
        default_factory=list,
        description="Diagnoses or conditions the patient is stated to have.",
    )
    symptoms: list[str] = Field(default_factory=list)
    actions: list[Action] = Field(
        description="update_history: they reported a diagnosis, medication, or past event worth "
        "saving. research: they want information about a condition or its treatment. "
        "book_appointment: they want to see a doctor. A described health concern with no other "
        "request implies research and book_appointment."
    )
    research: ResearchTopic | None = Field(
        default=None, description="Set when actions includes research."
    )
    specialty: str | None = Field(
        default=None,
        description="The best-fitting clinic specialty, exactly as listed, when it can be "
        "determined; otherwise null.",
    )
    urgency: Literal["routine", "urgent", "emergency"] = "routine"
    summary: str = Field(description="One neutral sentence restating the request.")


class PlanStep(BaseModel):
    agent: Agent = Field(
        description="history: identify the patient and read or update their records. "
        "research: look up a condition. booking: choose a doctor and book a time."
    )
    goal: str = Field(description="What this step should accomplish, in one sentence.")


class Plan(BaseModel):
    steps: list[PlanStep] = Field(description="Ordered steps; empty if nothing needs doing.")
