from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from app.config import settings
from app.tools.medlineplus_tools import medlineplus_search
from app.tools.who_tools import who_fact_sheet_search, who_gho_lookup

REFERENCE_SYSTEM_PROMPT = """You are a medical reference lookup agent used by doctors. You answer
clinical reference questions using medlineplus_search (MedlinePlus health topics),
who_fact_sheet_search (WHO fact sheets/guidance), and who_gho_lookup (WHO statistical
indicators).

Rules:
- Always cite your source (MedlinePlus or WHO) and include the URL for every claim you make.
- Only use information returned by your tools — do not answer from general knowledge alone for
  clinical claims.
- You are providing reference information, not a diagnosis or treatment plan for a specific
  patient. Do not phrase answers as medical advice directed at an individual patient.
- Be concise: a doctor wants a quick, well-cited answer, not an essay.
- Do not use emojis in your replies.
"""

DISCLAIMER = (
    "This information is for clinical reference only, sourced from WHO/MedlinePlus, "
    "and is not a diagnosis or treatment recommendation."
)


def build_reference_agent():
    model = ChatAnthropic(model=settings.sonnet_model, api_key=settings.anthropic_api_key)
    return create_react_agent(
        model=model,
        tools=[medlineplus_search, who_fact_sheet_search, who_gho_lookup],
        prompt=REFERENCE_SYSTEM_PROMPT,
        name="reference_agent",
    )
