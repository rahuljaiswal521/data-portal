"""ChromaDB embedding service for RAG retrieval."""

import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings

logger = logging.getLogger(__name__)

# Embedding function loaded once, shared across calls
_embedding_fn = None


def _get_embedding_function():
    """Lazy-load sentence-transformers embedding function."""
    global _embedding_fn
    if _embedding_fn is None:
        from chromadb.utils.embedding_functions import (
            SentenceTransformerEmbeddingFunction,
        )

        _embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        logger.info("Loaded embedding model: all-MiniLM-L6-v2")
    return _embedding_fn


class EmbeddingService:
    """Manages ChromaDB collections with tenant isolation.

    Collection naming:
        - "shared_docs"             — framework docs (all tenants share)
        - "tenant_{id}_sources"     — tenant-specific source configs
    """

    SHARED_COLLECTION = "shared_docs"

    def __init__(self) -> None:
        persist_dir = Path(settings.chromadb_persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._ef = _get_embedding_function()

    def _get_or_create_collection(self, name: str):
        return self._client.get_or_create_collection(
            name=name,
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

    def _tenant_collection_name(self, tenant_id: str) -> str:
        return f"tenant_{tenant_id}_sources"

    # ── Indexing ──

    def index_documents(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> int:
        """Upsert documents into a ChromaDB collection. Returns count indexed."""
        collection = self._get_or_create_collection(collection_name)
        collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )
        logger.info("Indexed %d documents into '%s'", len(documents), collection_name)
        return len(documents)

    def index_shared_docs(self, doc_chunks: list[dict]) -> int:
        """Index framework documentation into shared collection.

        Each chunk: {"id": str, "text": str, "metadata": dict}
        """
        if not doc_chunks:
            return 0
        return self.index_documents(
            self.SHARED_COLLECTION,
            documents=[c["text"] for c in doc_chunks],
            metadatas=[c["metadata"] for c in doc_chunks],
            ids=[c["id"] for c in doc_chunks],
        )

    def index_tenant_sources(
        self, tenant_id: str, source_chunks: list[dict]
    ) -> int:
        """Index tenant YAML source configs.

        Each chunk: {"id": str, "text": str, "metadata": dict}
        """
        if not source_chunks:
            return 0
        collection_name = self._tenant_collection_name(tenant_id)
        return self.index_documents(
            collection_name,
            documents=[c["text"] for c in source_chunks],
            metadatas=[c["metadata"] for c in source_chunks],
            ids=[c["id"] for c in source_chunks],
        )

    def clear_tenant_sources(self, tenant_id: str) -> None:
        """Delete all documents from a tenant's source collection."""
        name = self._tenant_collection_name(tenant_id)
        try:
            self._client.delete_collection(name)
            logger.info("Cleared tenant collection: %s", name)
        except Exception:
            pass  # collection doesn't exist

    # ── Retrieval ──

    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
    ) -> list[dict]:
        """Query a collection, return list of {text, metadata, distance}."""
        try:
            collection = self._client.get_collection(
                name=collection_name,
                embedding_function=self._ef,
            )
        except Exception:
            return []

        results = collection.query(
            query_texts=[query_text],
            n_results=min(n_results, collection.count() or 1),
        )

        hits = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                hits.append(
                    {
                        "text": doc,
                        "metadata": (
                            results["metadatas"][0][i] if results["metadatas"] else {}
                        ),
                        "distance": (
                            results["distances"][0][i] if results["distances"] else 0.0
                        ),
                    }
                )
        return hits

    def query_tenant_and_shared(
        self,
        tenant_id: str,
        query_text: str,
        n_results: int = 5,
    ) -> list[dict]:
        """Query both tenant sources + shared docs, merge and rank."""
        tenant_hits = self.query(
            self._tenant_collection_name(tenant_id),
            query_text,
            n_results=n_results,
        )
        shared_hits = self.query(
            self.SHARED_COLLECTION,
            query_text,
            n_results=n_results,
        )
        # Merge, sort by distance (lower = better for cosine)
        all_hits = tenant_hits + shared_hits
        all_hits.sort(key=lambda h: h["distance"])
        return all_hits[:n_results]

    # ── Status ──

    def get_index_status(self, tenant_id: str) -> dict:
        shared_count = 0
        tenant_count = 0
        try:
            c = self._client.get_collection(
                self.SHARED_COLLECTION, embedding_function=self._ef
            )
            shared_count = c.count()
        except Exception:
            pass
        try:
            c = self._client.get_collection(
                self._tenant_collection_name(tenant_id),
                embedding_function=self._ef,
            )
            tenant_count = c.count()
        except Exception:
            pass
        return {
            "shared_doc_chunks": shared_count,
            "tenant_source_chunks": tenant_count,
        }
