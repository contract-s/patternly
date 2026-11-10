"""Pattern notes in Postgres: one row per note section, with an embedding and a full-text index."""

from __future__ import annotations

import os
from dataclasses import dataclass

import psycopg
from pgvector.psycopg import register_vector

from ..content.loader import Content
from .models import Embedder

DEFAULT_DATABASE_URL = "postgresql://patternly:patternly@localhost:5433/patternly"


@dataclass(frozen=True)
class Chunk:
    pattern: str
    section: str
    text: str


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def connect(url: str | None = None) -> psycopg.Connection:
    conn = psycopg.connect(url or database_url(), autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    return conn


def create_schema(conn: psycopg.Connection, dim: int) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS note_chunks (
            id        serial PRIMARY KEY,
            pattern   text NOT NULL,
            section   text NOT NULL,
            text      text NOT NULL,
            embedding vector({dim}) NOT NULL,
            tsv       tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
            UNIQUE (pattern, section)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS note_chunks_tsv ON note_chunks USING gin (tsv)")
    # 90 rows: an exact scan is instant, so no approximate vector index is needed yet.


def chunks_from_notes(content: Content) -> list[Chunk]:
    """One chunk per note section, prefixed with the note title so each chunk stands alone."""
    out = []
    for pid in sorted(content.notes):
        note = content.notes[pid]
        for heading, body in note.sections.items():
            out.append(Chunk(pid, heading, f"{note.title}: {heading}\n\n{body}"))
    return out


def index_notes(conn: psycopg.Connection, content: Content, embedder: Embedder) -> int:
    """Replace every stored chunk with the current notes. Returns the number of chunks."""
    chunks = chunks_from_notes(content)
    vectors = embedder.passages([c.text for c in chunks])
    create_schema(conn, embedder.dim)
    with conn.transaction():
        conn.execute("DELETE FROM note_chunks")
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO note_chunks (pattern, section, text, embedding) VALUES (%s, %s, %s, %s)",
                [(c.pattern, c.section, c.text, v) for c, v in zip(chunks, vectors, strict=True)],
            )
    return len(chunks)


def vector_search(conn: psycopg.Connection, query_vec: list[float], limit: int) -> list[Chunk]:
    import numpy as np

    rows = conn.execute(
        "SELECT pattern, section, text FROM note_chunks ORDER BY embedding <=> %s LIMIT %s",
        (np.array(query_vec, dtype=np.float32), limit),
    ).fetchall()
    return [Chunk(*r) for r in rows]


def keyword_search(conn: psycopg.Connection, query: str, limit: int) -> list[Chunk]:
    """Full-text search that ORs the query's words, so a long answer still matches.

    `plainto_tsquery` would AND every word of a paragraph-long answer and match nothing.
    """
    rows = conn.execute(
        """
        WITH q AS (
            SELECT to_tsquery('english', string_agg(quote_literal(lexeme), ' | ')) AS query
            FROM unnest(to_tsvector('english', %s))
        )
        SELECT pattern, section, text
        FROM note_chunks, q
        WHERE q.query IS NOT NULL AND tsv @@ q.query
        ORDER BY ts_rank(tsv, q.query) DESC, id
        LIMIT %s
        """,
        (query, limit),
    ).fetchall()
    return [Chunk(*r) for r in rows]
