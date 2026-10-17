"""Compose chain: merges what the history agent, research tool, and booking agent
produced this turn into a single reply."""
import re
from functools import lru_cache

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.config import settings

RESEARCH_PLACEHOLDER = "[[RESEARCH]]"

COMPOSE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You assemble one reply for a patient from parts written by a clinic's specialist "
            "assistants. Rules:\n"
            "- Keep every fact, name, date, time, and question exactly as given; never invent, "
            "change, or add information.\n"
            "- Order the reply: first a short summary of the patient's history (condense it to "
            "two or three lines and drop greetings), then the research, then the booking "
            "question or confirmation, so the reply ends with what the patient needs to answer.\n"
            "- If a research part is present it appears as the token " + RESEARCH_PLACEHOLDER
            + ". Put that token on its own line where the research belongs and do not rewrite "
            "it. If there is no research part, never write the token.\n"
            "- Keep the voice consistent with who is chatting: address them as 'you'; when they "
            "are asking for someone else, refer to the patient by name or as he, she, or they, "
            "never as 'you'.\n"
            "- Remove any mention of other teams, steps, tools, or handing off, and any repeated "
            "sentences.\n"
            "- Write plain text for a chat window: no markdown, no emojis. Use short lines and "
            "'-' for lists. Do not add a disclaimer.",
        ),
        (
            "human",
            "Patient's latest message:\n{message}\n\nWho is chatting: {audience}\n\n"
            "Parts, in order:\n{parts}\n\nWrite the reply.",
        ),
    ]
)


@lru_cache
def _chain():
    model = ChatAnthropic(model=settings.haiku_model, api_key=settings.anthropic_api_key)
    return COMPOSE_PROMPT | model | StrOutputParser()


def compose(message: str, sections: list[tuple[str, str]], audience: str) -> str:
    """sections are (label, text) pairs in plan order, with the research text
    labeled "research". The research text is inserted verbatim afterwards so
    its citations can't be altered."""
    research = next((text for label, text in sections if label == "research"), None)
    shown = "\n\n".join(
        f"[{label}]\n{RESEARCH_PLACEHOLDER if label == 'research' else text}"
        for label, text in sections
    )
    reply = _chain().invoke({"message": message, "audience": audience, "parts": shown}).strip()

    if research is None:
        return re.sub(r"\n{3,}", "\n\n", reply.replace(RESEARCH_PLACEHOLDER, "")).strip()
    if RESEARCH_PLACEHOLDER in reply:
        merged = reply.replace(RESEARCH_PLACEHOLDER, research)
    else:
        first, _, rest = reply.partition("\n\n")
        merged = "\n\n".join(part for part in (first, research, rest) if part)
    return re.sub(r"\n{3,}", "\n\n", merged).strip()
