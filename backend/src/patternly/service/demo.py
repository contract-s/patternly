"""Limits that keep a public demo cheap: a daily tutor budget, a per-learner cap, and sign-ups per IP.

Every limit is off unless its environment variable is set, so local development is unchanged.

- PATTERNLY_DAILY_BUDGET_USD: once the tutor's spend since midnight UTC reaches this, attempts are graded by
  the free offline grader until the next UTC day.
- PATTERNLY_TUTOR_ATTEMPTS_PER_LEARNER: tutor-graded attempts per learner per UTC day; later attempts that day
  use the offline grader too.
- PATTERNLY_SIGNUPS_PER_IP_PER_HOUR: accounts (registered or guest) one IP address can create per hour.
- PATTERNLY_PROXY_HOPS: how many proxies append to X-Forwarded-For in front of the API (1 for nginx alone,
  2 for CloudFront then nginx), so the client address is read from the right entry.

Two attempts that check the budget at the same moment can both go to the tutor, so the budget can be exceeded
by a few attempts. A spend limit on the API key is the hard ceiling.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime

from psycopg import AsyncConnection


def _env_number(name: str, kind: type) -> float | int | None:
    raw = os.environ.get(name, "").strip()
    return kind(raw) if raw else None


@dataclass(frozen=True)
class DemoLimits:
    daily_budget_usd: float | None = None
    tutor_attempts_per_learner: int | None = None
    signups_per_ip_per_hour: int | None = None
    proxy_hops: int = 1

    @classmethod
    def from_env(cls) -> DemoLimits:
        return cls(
            daily_budget_usd=_env_number("PATTERNLY_DAILY_BUDGET_USD", float),
            tutor_attempts_per_learner=_env_number("PATTERNLY_TUTOR_ATTEMPTS_PER_LEARNER", int),
            signups_per_ip_per_hour=_env_number("PATTERNLY_SIGNUPS_PER_IP_PER_HOUR", int),
            proxy_hops=_env_number("PATTERNLY_PROXY_HOPS", int) or 1,
        )


def utc_day_start(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


async def tutor_allowed(conn: AsyncConnection, learner_id: int, now: datetime, limits: DemoLimits) -> bool:
    """Whether this attempt may use the paid tutor, given today's spend and the learner's tutor attempts."""
    if limits.daily_budget_usd is None and limits.tutor_attempts_per_learner is None:
        return True
    cur = await conn.execute(
        """SELECT coalesce(sum(a.cost_usd), 0), count(*) FILTER (WHERE l.learner_id = %s AND a.graded_by = 'tutor')
           FROM attempts a JOIN lessons l ON l.id = a.lesson_id WHERE a.created_at >= %s""",
        (learner_id, utc_day_start(now)),
    )
    spent, mine = await cur.fetchone()
    if limits.daily_budget_usd is not None and spent >= limits.daily_budget_usd:
        return False
    return limits.tutor_attempts_per_learner is None or mine < limits.tutor_attempts_per_learner


def client_ip(forwarded_for: str | None, peer: str | None, proxy_hops: int) -> str:
    """The client's address: the entry `proxy_hops` from the end of X-Forwarded-For (entries before it can be
    set by the client), or the socket peer when there's no header."""
    entries = [e.strip() for e in (forwarded_for or "").split(",") if e.strip()]
    if len(entries) >= proxy_hops:
        return entries[-proxy_hops]
    return entries[0] if entries else (peer or "unknown")


class SignupLimiter:
    """Accounts created per IP in a sliding hour, in memory (one API process)."""

    def __init__(self, per_hour: int | None, clock=time.monotonic) -> None:
        self.per_hour = per_hour
        self.clock = clock
        self._seen: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, ip: str) -> bool:
        if self.per_hour is None:
            return True
        now = self.clock()
        with self._lock:
            q = self._seen[ip]
            while q and now - q[0] >= 3600:
                q.popleft()
            if len(q) >= self.per_hour:
                return False
            q.append(now)
            return True
