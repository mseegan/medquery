"""Shows the assistant's plain-text replies in Streamlit: readable line breaks,
section labels in bold, and the Sources list as clickable links."""
import re

import streamlit as st

from app.agents.prompts import DISCLAIMER

SECTION_LABELS = (
    "Overview",
    "Current treatment approaches",
    "Recent developments",
    "Questions to ask a doctor",
)
SOURCE_LINE = re.compile(r"^\[(\d+)\]\s+(.*?)\s+-\s+(https?://\S+)\s*$")


def split_sources(text: str) -> tuple[str, list[str]]:
    """The reply body and the lines of its trailing Sources list."""
    body, marker, tail = text.partition("\nSources:\n")
    sources = [line for line in tail.splitlines() if line.strip()] if marker else []
    return body.strip(), sources


def to_markdown(text: str) -> str:
    text = text.replace("$", r"\$")  # a bare $ would start a math expression
    lines = [f"**{line}**" if line.strip() in SECTION_LABELS else line for line in text.splitlines()]
    return "  \n".join(lines)  # keep the reply's own line breaks


def source_markdown(line: str) -> str:
    match = SOURCE_LINE.match(line)
    if not match:
        return line.replace("$", r"\$")
    number, title, url = match.groups()
    return f"[{number}] [{title.replace('$', chr(92) + '$')}]({url})"


def show_message(text: str, used_reference: bool = False) -> None:
    body, sources = split_sources(text)
    st.markdown(to_markdown(body))
    if sources:
        with st.expander(f"Sources ({len(sources)})"):
            for line in sources:
                st.markdown(source_markdown(line))
    if used_reference:
        st.caption(DISCLAIMER)
