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


def split_reply(text: str) -> tuple[str, list[str], str]:
    """The text before the Sources list, the list's numbered lines, and any text
    after it (such as a booking question that follows the research)."""
    lines = text.splitlines()
    if "Sources:" not in lines:
        return text.strip(), [], ""
    marker = lines.index("Sources:")
    end = marker + 1
    while end < len(lines) and SOURCE_LINE.match(lines[end]):
        end += 1
    return (
        "\n".join(lines[:marker]).strip(),
        lines[marker + 1 : end],
        "\n".join(lines[end:]).strip(),
    )


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
    before, sources, after = split_reply(text)
    st.markdown(to_markdown(before))
    if sources:
        with st.expander(f"Sources ({len(sources)})"):
            for line in sources:
                st.markdown(source_markdown(line))
    if used_reference:
        st.caption(DISCLAIMER)
    if after:
        st.markdown(to_markdown(after))
