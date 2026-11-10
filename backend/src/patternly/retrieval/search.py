"""Four ways to retrieve notes, so they can be compared: vector, keyword, hybrid, hybrid + rerank."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .models import Embedder, Reranker
from .store import Chunk, keyword_search, vector_search

METHODS = ["vector", "keyword", "hybrid", "hybrid-rerank"]
CANDIDATES = 30  # chunks taken from each search before fusing
RERANK_POOL = 20  # fused chunks the reranker reorders
RRF_K = 60  # standard reciprocal-rank-fusion constant


def rrf(*rankings: list[Chunk], k: int = RRF_K) -> list[Chunk]:
    """Reciprocal rank fusion: score each chunk by the sum of 1 / (k + rank) over the lists it's in."""
    scores: dict[tuple[str, str], float] = {}
    chunk_by_key: dict[tuple[str, str], Chunk] = {}
    for ranking in rankings:
        for rank, c in enumerate(ranking, start=1):
            key = (c.pattern, c.section)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            chunk_by_key[key] = c
    return [chunk_by_key[key] for key in sorted(scores, key=lambda key: -scores[key])]


def top_patterns(chunks: list[Chunk], k: int) -> list[str]:
    """Distinct patterns in the order their first chunk appears."""
    out: list[str] = []
    for c in chunks:
        if c.pattern not in out:
            out.append(c.pattern)
            if len(out) == k:
                break
    return out


@dataclass
class Retriever:
    conn: object
    embedder: Embedder
    reranker: Reranker | None = None
    vector_fn: Callable = vector_search
    keyword_fn: Callable = keyword_search

    def search(self, query: str, method: str = "hybrid-rerank", limit: int = 10) -> list[Chunk]:
        if method == "vector":
            return self.vector_fn(self.conn, self.embedder.query(query), limit)
        if method == "keyword":
            return self.keyword_fn(self.conn, query, limit)
        fused = rrf(
            self.vector_fn(self.conn, self.embedder.query(query), CANDIDATES),
            self.keyword_fn(self.conn, query, CANDIDATES),
        )
        if method == "hybrid":
            return fused[:limit]
        if method == "hybrid-rerank":
            if self.reranker is None:
                raise ValueError("hybrid-rerank needs a reranker")
            pool = fused[:RERANK_POOL]
            scores = self.reranker.scores(query, [c.text for c in pool])
            ranked = [c for _, c in sorted(zip(scores, pool, strict=True), key=lambda p: -p[0])]
            return ranked[:limit]
        raise ValueError(f"unknown method '{method}'")
