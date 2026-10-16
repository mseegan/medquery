"""Long-term patient memory over the vector store.

Three kinds of entries, all tagged with a patient_id:
  summary - the patient's current generated summary (one per patient)
  record  - text imported from the patient records spreadsheet
  memory  - facts learned in conversation
"""
import uuid
from datetime import datetime

from langchain_core.documents import Document

from app.memory.vector_store import get_store

SUMMARY, RECORD, MEMORY = "summary", "record", "memory"


def _metadata(patient_id: str, kind: str, source: str) -> dict:
    return {
        "patient_id": patient_id,
        "kind": kind,
        "source": source,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def _summary_id(patient_id: str) -> str:
    return f"{SUMMARY}:{patient_id}"


def index_summary(patient_id: str, text: str) -> None:
    """Store the patient's current summary, replacing the previous one."""
    get_store().add_documents(
        [Document(page_content=text, metadata=_metadata(patient_id, SUMMARY, "generated"))],
        ids=[_summary_id(patient_id)],
    )


def index_record(patient_id: str, text: str, source: str) -> None:
    """Store imported record text, replacing earlier text from the same source."""
    get_store().add_documents(
        [Document(page_content=text, metadata=_metadata(patient_id, RECORD, source))],
        ids=[f"{RECORD}:{patient_id}:{source}"],
    )


def remember(
    patient_id: str, text: str, source: str = "conversation", key: str | None = None
) -> str:
    """Store a long-term fact about the patient. With a key, a later call with the
    same key replaces the earlier note instead of adding another. Returns the id."""
    memory_id = f"{MEMORY}:{patient_id}:{key or uuid.uuid4().hex[:8]}"
    get_store().add_documents(
        [Document(page_content=text, metadata=_metadata(patient_id, MEMORY, source))],
        ids=[memory_id],
    )
    return memory_id


def get_summary(patient_id: str) -> str:
    found = get_store().get(ids=[_summary_id(patient_id)])
    return found["documents"][0] if found["documents"] else ""


def get_imported(patient_id: str) -> str:
    """The patient's imported record text, if any was indexed."""
    found = get_store().get(where={"$and": [{"patient_id": patient_id}, {"kind": RECORD}]})
    return "\n".join(found["documents"])


def recall(
    patient_id: str, query: str, k: int = 4, kinds: list[str] | None = None
) -> list[Document]:
    """The entries most relevant to the query, for this patient only."""
    where: dict = {"patient_id": patient_id}
    if kinds:
        where = {"$and": [where, {"kind": {"$in": kinds}}]}
    return get_store().similarity_search(query or "patient history", k=k, filter=where)


def patient_context(patient_id: str | None, query: str = "", k: int = 4) -> str:
    """Prompt-ready text of what is known about a patient: their current
    summary plus the notes most relevant to the query. Empty if nothing is known."""
    if not patient_id:
        return ""

    lines = []
    summary = get_summary(patient_id)
    if summary:
        lines.append(f"Summary: {summary}")

    related = recall(patient_id, query, k=k, kinds=[RECORD, MEMORY])
    if related:
        lines.append("Relevant notes:")
        for doc in related:
            label = "imported record" if doc.metadata["kind"] == RECORD else "remembered"
            lines.append(f"- ({label}) {doc.page_content}")

    if not lines:
        return ""
    return "What is known about this patient from long-term memory:\n" + "\n".join(lines)
