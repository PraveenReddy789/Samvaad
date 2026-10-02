import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from backend.config import DATA_DIR


class BM25RetrieverManager:
    """Manages sparse BM25 indexing and keyword retrieval."""

    def __init__(self, index_path: Optional[str] = None):
        self.index_path = Path(index_path or (DATA_DIR / "bm25_index.json"))
        self.chunks: List[Dict[str, Any]] = []
        self.bm25: Optional[BM25Okapi] = None
        self.load_index()

    def _tokenize(self, text: str) -> List[str]:
        """Simple, robust regex tokenizer for BM25."""
        return re.findall(r"\b\w+\b", text.lower())

    def index_chunks(self, chunks: List[Dict[str, Any]]):
        """Indexes document chunks into BM25 and persists to disk."""
        self.chunks = chunks
        tokenized_corpus = [self._tokenize(c["text"]) for c in chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)
        self.save_index()

    def search_sparse(
        self,
        query: str,
        limit: int = 10,
        filter_status: Optional[str] = "Active"
    ) -> List[Dict[str, Any]]:
        """Searches using BM25 with optional status filtering."""
        if not self.bm25 or not self.chunks:
            return []

        tokenized_query = self._tokenize(query)
        if not tokenized_query:
            return []

        scores = self.bm25.get_scores(tokenized_query)
        scored_pairs = list(enumerate(scores))
        scored_pairs.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in scored_pairs:
            if score <= 0.0:
                continue

            chunk = self.chunks[idx]
            status = chunk.get("metadata", {}).get("status")
            if filter_status and status and status != filter_status:
                continue

            results.append({
                "id": chunk.get("id"),
                "score": float(score),
                "text": chunk["text"],
                "metadata": chunk.get("metadata", {})
            })

            if len(results) >= limit:
                break

        return results

    def save_index(self):
        """Persists the chunk corpus for BM25."""
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, ensure_ascii=False, indent=2)

    def load_index(self):
        """Loads chunks and rebuilds BM25 model if index file exists."""
        if self.index_path.exists():
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    self.chunks = json.load(f)
                if self.chunks:
                    tokenized_corpus = [self._tokenize(c["text"]) for c in self.chunks]
                    self.bm25 = BM25Okapi(tokenized_corpus)
            except Exception as e:
                print(f"[Warning] Failed loading BM25 index: {e}")


_bm25_instance = None


def get_bm25_retriever() -> BM25RetrieverManager:
    global _bm25_instance
    if _bm25_instance is None:
        _bm25_instance = BM25RetrieverManager()
    return _bm25_instance
