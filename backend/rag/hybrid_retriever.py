from typing import List, Dict, Any, Optional
from backend.rag.vectorstore import get_vector_store
from backend.rag.bm25_retriever import get_bm25_retriever
from backend.rag.reranker import get_reranker


class HybridRetriever:
    """
    Orchestrates Dense Qdrant retrieval + Sparse BM25 retrieval,
    fuses candidate results via Reciprocal Rank Fusion (RRF),
    and applies reranking to produce top grounded context chunks.
    """

    def __init__(self):
        self.vector_store = get_vector_store()
        self.bm25 = get_bm25_retriever()
        self.reranker = get_reranker()

    def search(
        self,
        query: str,
        top_k: int = 4,
        candidate_pool: int = 15,
        filter_status: Optional[str] = "Active"
    ) -> List[Dict[str, Any]]:
        """
        Executes hybrid retrieval:
        1. Dense retrieval (Qdrant)
        2. Sparse retrieval (BM25)
        3. Reciprocal Rank Fusion (RRF)
        4. Cross-Encoder Reranking
        """
        # 1. Dense retrieval
        dense_results = self.vector_store.search_dense(
            query=query,
            limit=candidate_pool,
            filter_status=filter_status
        )

        # 2. Sparse BM25 retrieval
        sparse_results = self.bm25.search_sparse(
            query=query,
            limit=candidate_pool,
            filter_status=filter_status
        )

        # 3. Reciprocal Rank Fusion (RRF)
        rrf_k = 60
        fused_scores: Dict[str, float] = {}
        items_by_id: Dict[str, Dict[str, Any]] = {}

        # Add dense ranks
        for rank, item in enumerate(dense_results):
            doc_id = item["id"]
            rrf_score = 1.0 / (rrf_k + rank + 1)
            fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + rrf_score
            items_by_id[doc_id] = item

        # Add sparse ranks
        for rank, item in enumerate(sparse_results):
            doc_id = item["id"]
            rrf_score = 1.0 / (rrf_k + rank + 1)
            fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + rrf_score
            if doc_id not in items_by_id:
                items_by_id[doc_id] = item

        # Sort by fused RRF score
        candidates = []
        for doc_id, score in sorted(fused_scores.items(), key=lambda x: x[1], reverse=True):
            entry = dict(items_by_id[doc_id])
            entry["rrf_score"] = round(score, 5)
            candidates.append(entry)

        # 4. Reranking
        reranked = self.reranker.rerank(query=query, candidates=candidates, top_k=top_k)
        return reranked


_retriever_instance = None


def get_hybrid_retriever() -> HybridRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = HybridRetriever()
    return _retriever_instance
