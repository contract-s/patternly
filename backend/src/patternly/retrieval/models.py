"""Local embedding and reranking models (ONNX via fastembed, no API key).

Weights download from Hugging Face on first use and are cached afterwards.
"""

from __future__ import annotations

from functools import cached_property
from typing import Protocol

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384
RERANK_MODEL = "BAAI/bge-reranker-base"


class Embedder(Protocol):
    dim: int

    def passages(self, texts: list[str]) -> list[list[float]]: ...

    def query(self, text: str) -> list[float]: ...


class Reranker(Protocol):
    def scores(self, query: str, texts: list[str]) -> list[float]: ...


class LocalEmbedder:
    dim = EMBED_DIM

    def __init__(self, model: str = EMBED_MODEL) -> None:
        self.model_name = model

    @cached_property
    def _model(self):
        from fastembed import TextEmbedding

        return TextEmbedding(self.model_name)

    def passages(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.passage_embed(texts)]

    def query(self, text: str) -> list[float]:
        # query_embed adds the model's search-query instruction where it has one.
        return next(iter(self._model.query_embed(text))).tolist()


class LocalReranker:
    def __init__(self, model: str = RERANK_MODEL) -> None:
        self.model_name = model

    @cached_property
    def _model(self):
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        return TextCrossEncoder(self.model_name)

    def scores(self, query: str, texts: list[str]) -> list[float]:
        return [float(s) for s in self._model.rerank(query, texts)]
