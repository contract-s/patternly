"""Retrieval logic without models or a database: fusion, pattern ranking, method wiring, eval math."""

from __future__ import annotations

import pytest

from patternly.evals.retrieval import make_query, summarize
from patternly.retrieval.search import Retriever, rrf, top_patterns
from patternly.retrieval.store import Chunk


def c(pattern: str, section: str = "Steps") -> Chunk:
    return Chunk(pattern, section, f"{pattern} {section}")


def test_rrf_rewards_chunks_found_by_both_searches():
    a, b, x, y = c("a"), c("b"), c("x"), c("y")
    fused = rrf([x, a, b], [y, a, b])
    assert fused[:2] == [a, b]  # in both lists, so they beat chunks that top only one
    assert set(fused) == {a, b, x, y}


def test_top_patterns_dedupes_in_order():
    chunks = [c("a", "Steps"), c("a", "Cost"), c("b"), c("c"), c("d")]
    assert top_patterns(chunks, 3) == ["a", "b", "c"]


class FakeEmbedder:
    dim = 2

    def passages(self, texts):
        return [[0.0, 0.0] for _ in texts]

    def query(self, text):
        return [1.0, 0.0]


class FakeReranker:
    def scores(self, query, texts):
        return [1.0 if t.startswith("z") else 0.0 for t in texts]


def make_retriever(reranker=None):
    return Retriever(
        conn=None,
        embedder=FakeEmbedder(),
        reranker=reranker,
        vector_fn=lambda conn, vec, limit: [c("v1"), c("both"), c("z")][:limit],
        keyword_fn=lambda conn, q, limit: [c("k1"), c("both")][:limit],
    )


def test_methods():
    r = make_retriever(FakeReranker())
    assert [x.pattern for x in r.search("q", "vector", 2)] == ["v1", "both"]
    assert [x.pattern for x in r.search("q", "keyword", 5)] == ["k1", "both"]
    assert r.search("q", "hybrid", 1)[0].pattern == "both"
    assert r.search("q", "hybrid-rerank", 1)[0].pattern == "z"
    with pytest.raises(ValueError):
        make_retriever().search("q", "hybrid-rerank")
    with pytest.raises(ValueError):
        r.search("q", "nope")


def test_make_query_forms():
    assert make_query("answer", "P", "A") == "A"
    assert make_query("scenario+answer", " P \n", "A") == "P\n\nA"


def test_summary_hit_rates():
    def rec(rank, kind="correct"):
        return {"form": "answer", "method": "vector", "kind": kind, "rank": rank, "latency_s": 0.01}

    s = summarize([rec(1), rec(3), rec(4, "vague"), rec(None, "vague")])["answer | vector"]
    assert s["hit_at_1"] == 0.25 and s["hit_at_3"] == 0.5
    assert s["mrr"] == pytest.approx((1 + 1 / 3 + 1 / 4 + 0) / 4)
    assert s["hit_at_3_by_kind"] == {"correct": 1.0, "vague": 0.0}
