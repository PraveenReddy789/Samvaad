import uuid
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from backend.config import QDRANT_STORAGE_PATH, QDRANT_COLLECTION, QDRANT_HOST, QDRANT_PORT
from backend.rag.embeddings import get_embeddings


class QdrantVectorStoreManager:
    """Manages Qdrant vector storage and dense retrieval for RAG knowledge base."""

    def __init__(self):
        if QDRANT_HOST:
            try:
                self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=2.0)
                self.client.get_collections()
            except Exception as e:
                print(f"[Warning] Could not connect to remote Qdrant at {QDRANT_HOST}:{QDRANT_PORT}: {e}. Falling back to local storage: {QDRANT_STORAGE_PATH}")
                self.client = QdrantClient(path=QDRANT_STORAGE_PATH)
        else:
            self.client = QdrantClient(path=QDRANT_STORAGE_PATH)

        self.collection_name = QDRANT_COLLECTION
        self.embeddings = get_embeddings()
        self._ensure_collection()

    def _ensure_collection(self):
        """Ensures the collection exists with cosine distance and 1024 dimensions."""
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
            )

    def upsert_chunks(self, chunks: List[Dict[str, Any]]):
        """
        Chunks format:
        [
            {
                "id": str,
                "text": str,
                "metadata": {
                    "source": str,
                    "title": str,
                    "doc_type": str,   # "policy", "sop", "product", "call"
                    "version": float / str,
                    "status": str,     # "Active" or "Retired"
                    "chunk_id": int
                }
            }
        ]
        """
        if not chunks:
            return

        texts = [c["text"] for c in chunks]
        vectors = self.embeddings.embed_documents(texts)

        points = []
        for i, chunk in enumerate(chunks):
            point_id = chunk.get("id") or str(uuid.uuid4())
            payload = {
                "text": chunk["text"],
                **chunk.get("metadata", {})
            }
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vectors[i],
                    payload=payload
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

    def search_dense(
        self,
        query: str,
        limit: int = 10,
        filter_status: Optional[str] = "Active"
    ) -> List[Dict[str, Any]]:
        """Dense similarity search using 1024d embeddings with payload filtering."""
        query_vector = self.embeddings.embed_query(query)
        
        qdrant_filter = None
        if filter_status:
            # We filter out retired documents when looking for active policies
            qdrant_filter = Filter(
                must=[
                    FieldCondition(
                        key="status",
                        match=MatchValue(value=filter_status)
                    )
                ]
            )

        # Qdrant client query_points / search
        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=qdrant_filter,
                limit=limit
            ).points
        except Exception:
            # Fallback to search method if query_points signature differs
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=qdrant_filter,
                limit=limit
            )

        formatted = []
        for res in results:
            formatted.append({
                "id": str(res.id),
                "score": float(res.score),
                "text": res.payload.get("text", ""),
                "metadata": {k: v for k, v in res.payload.items() if k != "text"}
            })
        return formatted


_vector_store_instance = None


def get_vector_store() -> QdrantVectorStoreManager:
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = QdrantVectorStoreManager()
    return _vector_store_instance
