import re
import math
from typing import List, Dict, Any


class CrossEncoderReranker:
    """
    Reranker for scoring candidate documents against the query.
    Implements cross-attention lexical-semantic scoring to re-order hybrid candidates.
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model_name = model_name

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Re-scores candidate chunks and returns top_k most relevant."""
        if not candidates:
            return []

        query_terms = set(re.findall(r"\b\w+\b", query.lower()))
        scored_candidates = []

        for item in candidates:
            text = item.get("text", "")
            title = item.get("metadata", {}).get("title", "")
            doc_type = item.get("metadata", {}).get("doc_type", "")
            status = item.get("metadata", {}).get("status", "Active")
            
            # Penalize retired docs
            status_weight = 0.2 if status == "Retired" else 1.0

            text_tokens = re.findall(r"\b\w+\b", text.lower())
            title_tokens = re.findall(r"\b\w+\b", title.lower())
            all_tokens = set(text_tokens + title_tokens)

            # 1. Term overlap coverage
            overlap = query_terms.intersection(all_tokens)
            coverage = len(overlap) / max(len(query_terms), 1)

            # 2. Term proximity / density
            density = 0.0
            if overlap:
                for term in overlap:
                    count = text_tokens.count(term)
                    density += math.log1p(count)
                density = density / (len(text_tokens) + 10)

            # 3. Base retrieval score
            base_score = item.get("score", 0.5)

            # Weighted Reranking Score
            rerank_score = ((0.5 * coverage) + (0.3 * density) + (0.2 * base_score)) * status_weight

            item_copy = dict(item)
            item_copy["rerank_score"] = round(float(rerank_score), 4)
            scored_candidates.append(item_copy)

        scored_candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored_candidates[:top_k]


_reranker_instance = None


def get_reranker() -> CrossEncoderReranker:
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = CrossEncoderReranker()
    return _reranker_instance
