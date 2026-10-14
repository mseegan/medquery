"""Disease research chain: gather sources in parallel, number them, and have
the model write a short cited summary."""
from functools import lru_cache

from langchain_anthropic import ChatAnthropic
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough

from app.config import settings
from app.research.sources import medlineplus_docs, pubmed_docs, who_docs

SOURCE_CHARS = 1800

RESEARCH_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You write brief research summaries on a disease or condition for a clinic chat. "
            "Use only the numbered sources provided and cite them in brackets after each claim, "
            "like [1] or [2][3]. If the sources don't cover something, say so rather than "
            "filling in from memory. Write plain text of 250 words or fewer using these labeled "
            "sections: Overview; Current treatment approaches (short lines starting with '-'); "
            "Recent developments (from the PubMed reviews, with the year when given); Questions "
            "to ask a doctor (one line). Do not use markdown or emojis. This is general "
            "information, not a diagnosis or medical advice.",
        ),
        (
            "human",
            "Condition: {disease}\nFocus: {focus}\n\nSources:\n{context}\n\nWrite the summary.",
        ),
    ]
)

_sources = RunnableParallel(
    medlineplus=RunnableLambda(lambda x: medlineplus_docs(x["disease"])),
    pubmed=RunnableLambda(lambda x: pubmed_docs(x["disease"], x["focus"])),
    who=RunnableLambda(lambda x: who_docs(x["disease"], x["focus"])),
)


def _number_sources(inputs: dict) -> dict:
    docs: list[Document] = [d for group in inputs["found"].values() for d in group]
    context = "\n\n".join(
        f"[{i}] ({d.metadata['source']}) {d.metadata['title']}\n{d.page_content[:SOURCE_CHARS]}"
        for i, d in enumerate(docs, start=1)
    )
    citations = [
        f"[{i}] {d.metadata['source']}: {d.metadata['title']} - {d.metadata['url']}"
        for i, d in enumerate(docs, start=1)
    ]
    return {**inputs, "context": context, "citations": citations}


def _write_or_decline(inputs: dict) -> str:
    if not inputs["citations"]:
        return (
            f"I couldn't reach any medical sources for {inputs['disease']} right now. "
            "Please try again in a moment."
        )
    summary = (RESEARCH_PROMPT | _model() | StrOutputParser()).invoke(inputs).strip()
    return summary + "\n\nSources:\n" + "\n".join(inputs["citations"])


@lru_cache
def _model() -> ChatAnthropic:
    return ChatAnthropic(model=settings.sonnet_model, api_key=settings.anthropic_api_key)


research_chain = (
    RunnablePassthrough.assign(found=_sources)
    | RunnableLambda(_number_sources)
    | RunnableLambda(_write_or_decline)
)
