"""The patient vector store: a persistent Chroma collection of patient summaries,
imported records, and long-term memories, searched with a patient filter."""
from functools import lru_cache

from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from app.config import settings

COLLECTION = "patient_memory"


class LocalEmbeddings(Embeddings):
    """Chroma's bundled MiniLM model (ONNX), run locally with no API key. The
    model downloads once on first use."""

    def __init__(self) -> None:
        self._embed = DefaultEmbeddingFunction()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def build_store(persist_dir: str, collection: str = COLLECTION) -> Chroma:
    return Chroma(
        collection_name=collection,
        embedding_function=LocalEmbeddings(),
        persist_directory=persist_dir,
    )


@lru_cache
def get_store() -> Chroma:
    return build_store(settings.chroma_dir)
