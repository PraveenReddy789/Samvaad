import re
from typing import List, Dict, Any, Tuple
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
from backend.rag.vectorstore import PersistentVectorStore


def tokenize_text(text: str) -> List[str]:
    """Simple alphanumeric tokenizer for BM25 keyword matching."""
    return [token.lower() for token in re.findall(r"\w+", text) if len(token) > 1]


class HybridRetriever:
    """
    Hybrid Search combining:
    1. Dense Vector Search (Cosine Similarity on Mistral Embeddings)
    2. Sparse Keyword Search (BM25Okapi for exact terms, model names, specs, prices)
    3. Reciprocal Rank Fusion (RRF) to blend rankings.
    """

    def __init__(self, vector_store: PersistentVectorStore):
        self.vector_store = vector_store
        self.bm25: BM25Okapi | None = None
        self.corpus_docs: List[Document] = []
        self._build_bm25_index()

    def _build_bm25_index(self):
        """Builds BM25 index from current vector store documents."""
        self.corpus_docs = [
            Document(page_content=item["text"], metadata=item["metadata"])
            for item in self.vector_store.documents
        ]
        if self.corpus_docs:
            tokenized_corpus = [tokenize_text(doc.page_content) for doc in self.corpus_docs]
            self.bm25 = BM25Okapi(tokenized_corpus)
        else:
            self.bm25 = None

    def refresh(self):
        """Refreshes the BM25 index after new documents are added."""
        self._build_bm25_index()

    def get_relevant_documents(
        self,
        query: str,
        k: int = 5,
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4
    ) -> List[Tuple[Document, float]]:
        """
        Performs Hybrid Search using Reciprocal Rank Fusion (RRF).
        Returns top-k documents with combined relevance scores.
        """
        if not self.vector_store.documents:
            return []

        # 1. Dense Vector Retrieval
        vector_results = self.vector_store.similarity_search_with_score(query, k=k * 2)

        # 2. Sparse BM25 Keyword Retrieval
        bm25_results: List[Tuple[Document, float]] = []
        if self.bm25 is not None and len(self.corpus_docs) > 0:
            query_tokens = tokenize_text(query)
            if query_tokens:
                bm25_scores = self.bm25.get_scores(query_tokens)
                top_bm25_indices = sorted(
                    range(len(bm25_scores)),
                    key=lambda i: bm25_scores[i],
                    reverse=True
                )[:k * 2]
                for idx in top_bm25_indices:
                    if bm25_scores[idx] > 0:
                        bm25_results.append((self.corpus_docs[idx], float(bm25_scores[idx])))

        # 3. Reciprocal Rank Fusion (RRF)
        # RRF Score = sum( weight / (60 + rank) )
        doc_scores: Dict[str, Dict[str, Any]] = {}
        rrf_k = 60

        for rank, (doc, _) in enumerate(vector_results):
            key = doc.page_content[:150]
            if key not in doc_scores:
                doc_scores[key] = {"doc": doc, "score": 0.0}
            doc_scores[key]["score"] += vector_weight * (1.0 / (rrf_k + rank + 1))

        for rank, (doc, _) in enumerate(bm25_results):
            key = doc.page_content[:150]
            if key not in doc_scores:
                doc_scores[key] = {"doc": doc, "score": 0.0}
            doc_scores[key]["score"] += bm25_weight * (1.0 / (rrf_k + rank + 1))

        # Sort by fused score
        sorted_docs = sorted(doc_scores.values(), key=lambda x: x["score"], reverse=True)
        return [(item["doc"], item["score"]) for item in sorted_docs[:k]]
