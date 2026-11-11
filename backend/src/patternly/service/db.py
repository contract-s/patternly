"""Connection pool and schema setup for the service."""

from __future__ import annotations

from pathlib import Path

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from ..retrieval.store import database_url

SCHEMA = Path(__file__).with_name("schema.sql")


async def apply_schema(conn: AsyncConnection) -> None:
    await conn.execute(SCHEMA.read_text())


def make_pool(url: str | None = None) -> AsyncConnectionPool:
    # autocommit: each statement commits unless wrapped in `conn.transaction()`.
    return AsyncConnectionPool(url or database_url(), kwargs={"autocommit": True}, open=False, min_size=1, max_size=10)
