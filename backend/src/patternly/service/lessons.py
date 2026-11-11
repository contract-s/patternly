"""Lesson logic over Postgres: pick today's lesson, grade attempts, finish lessons, update progress."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from psycopg import AsyncConnection

from ..content.loader import Content
from ..content.models import Scenario
from ..learning.planner import plan
from ..learning.scheduler import Outcome, Progress, schedule
from ..learning.streaks import Streak, compute_streak
from ..tutor.agent import AttemptResult
from ..tutor.history import AttemptRecord, History, InMemoryHistory

MAX_ATTEMPTS = 4  # after this many failed attempts the pattern is revealed (about 10 minutes)

# Grades one attempt. Runs in a worker thread, since the tutor uses the synchronous API client.
Grader = Callable[[Scenario, str, History, str], AttemptResult]


class LessonError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def local_today(now: datetime, timezone: str) -> date:
    return now.astimezone(ZoneInfo(timezone)).date()


@dataclass
class Learner:
    id: int
    email: str
    timezone: str


async def get_progress(conn: AsyncConnection, learner_id: int) -> dict[str, Progress]:
    rows = await conn.execute(
        "SELECT pattern_id, box, due_date, reviews, last_outcome FROM pattern_progress WHERE learner_id = %s",
        (learner_id,),
    )
    return {r[0]: Progress(r[0], r[1], r[2], r[3], Outcome(r[4])) for r in await rows.fetchall()}


async def get_streak(conn: AsyncConnection, learner: Learner, now: datetime) -> Streak:
    rows = await conn.execute(
        "SELECT local_date FROM lessons WHERE learner_id = %s AND status <> 'open'", (learner.id,)
    )
    return compute_streak({r[0] for r in await rows.fetchall()}, local_today(now, learner.timezone))


async def todays_lesson(conn: AsyncConnection, content: Content, learner: Learner, now: datetime) -> dict:
    """Today's lesson row, created by the planner if it doesn't exist yet."""
    today = local_today(now, learner.timezone)
    row = await _lesson_row(conn, learner.id, today)
    if row is not None:
        return row
    scenarios_by_pattern: dict[str, list[str]] = {}
    for s in content.scenarios.values():
        scenarios_by_pattern.setdefault(s.pattern, []).append(s.id)
    seen = await conn.execute(
        "SELECT scenario_id, max(local_date) FROM lessons WHERE learner_id = %s GROUP BY scenario_id", (learner.id,)
    )
    pick = plan(
        today,
        list(content.patterns),
        scenarios_by_pattern,
        await get_progress(conn, learner.id),
        {r[0]: r[1] for r in await seen.fetchall()},
    )
    await conn.execute(
        """INSERT INTO lessons (learner_id, local_date, scenario_id, pattern_id, kind)
           VALUES (%s, %s, %s, %s, %s) ON CONFLICT (learner_id, local_date) DO NOTHING""",
        (learner.id, today, pick.scenario, pick.pattern, pick.kind),
    )
    return await _lesson_row(conn, learner.id, today)


_LESSON_COLS = "id, local_date, scenario_id, pattern_id, kind, status, outcome"


async def _lesson_row(conn: AsyncConnection, learner_id: int, day: date, lock: bool = False) -> dict | None:
    sql = f"SELECT {_LESSON_COLS} FROM lessons WHERE learner_id = %s AND local_date = %s"
    cur = await conn.execute(sql + (" FOR UPDATE NOWAIT" if lock else ""), (learner_id, day))
    r = await cur.fetchone()
    if r is None:
        return None
    return dict(zip(["id", "local_date", "scenario_id", "pattern_id", "kind", "status", "outcome"], r, strict=True))


async def lesson_attempts(conn: AsyncConnection, lesson_id: int) -> list[dict]:
    cur = await conn.execute(
        """SELECT attempt, answer, verdict, items, hint, hint_level FROM attempts
           WHERE lesson_id = %s ORDER BY attempt""",
        (lesson_id,),
    )
    keys = ["attempt", "answer", "verdict", "items", "hint", "hint_level"]
    return [dict(zip(keys, r, strict=True)) for r in await cur.fetchall()]


async def submit_attempt(
    conn: AsyncConnection, content: Content, learner: Learner, answer: str, now: datetime, grader: Grader
) -> tuple[dict, dict]:
    """Grade an answer to today's lesson. Returns (attempt row, lesson row after the attempt).

    Runs in one transaction with today's lesson locked, so two submissions can't race; a tutor error
    rolls everything back and nothing is saved.
    """
    import psycopg

    today = local_today(now, learner.timezone)
    async with conn.transaction():
        try:
            lesson = await _lesson_row(conn, learner.id, today, lock=True)
        except psycopg.errors.LockNotAvailable:
            raise LessonError(409, "An attempt for this lesson is already being graded.") from None
        if lesson is None:
            raise LessonError(404, "Open today's lesson first (GET /lessons/today).")
        if lesson["status"] != "open":
            raise LessonError(409, "Today's lesson is already finished. Come back tomorrow.")
        scenario = content.scenarios[lesson["scenario_id"]]
        prior = await lesson_attempts(conn, lesson["id"])
        # The tutor sees this lesson's attempts: they set the hint level and the hints already shown.
        history = InMemoryHistory()
        for p in prior:
            history.add(
                AttemptRecord(
                    str(learner.id), scenario.id, p["attempt"], p["verdict"], p["items"], p["hint"], p["hint_level"]
                )
            )
        result = await asyncio.to_thread(grader, scenario, answer, history, str(learner.id))
        if result.error or result.items is None:
            raise LessonError(502, f"The tutor couldn't grade this attempt: {result.error}")
        attempt = {
            "attempt": len(prior) + 1,
            "answer": answer,
            "verdict": result.verdict,
            "items": {c.rubric_id: c.hit for c in result.items},
            "hint": result.hint,
            "hint_level": result.hint_level,
        }
        await conn.execute(
            """INSERT INTO attempts (lesson_id, attempt, answer, verdict, items, hint, hint_level, hint_source,
                                     cost_usd, latency_s)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                lesson["id"],
                attempt["attempt"],
                answer,
                result.verdict,
                json.dumps(attempt["items"]),
                result.hint,
                result.hint_level,
                result.hint_source,
                result.cost_usd,
                result.latency_s,
            ),
        )
        outcome = None
        if result.verdict == "pass":
            outcome = Outcome.CLEAN if attempt["attempt"] == 1 else Outcome.HINTED
        elif attempt["attempt"] >= MAX_ATTEMPTS:
            outcome = Outcome.MISSED
        if outcome is not None:
            await _finish(conn, learner.id, lesson, outcome, today)
        lesson = await _lesson_row(conn, learner.id, today)
    return attempt, lesson


async def _finish(conn: AsyncConnection, learner_id: int, lesson: dict, outcome: Outcome, today: date) -> None:
    status = "revealed" if outcome == Outcome.MISSED else "passed"
    await conn.execute(
        "UPDATE lessons SET status = %s, outcome = %s, finished_at = now() WHERE id = %s",
        (status, outcome.value, lesson["id"]),
    )
    prev = (await get_progress(conn, learner_id)).get(lesson["pattern_id"])
    p = schedule(prev, lesson["pattern_id"], outcome, today)
    await conn.execute(
        """INSERT INTO pattern_progress (learner_id, pattern_id, box, due_date, reviews, last_outcome)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (learner_id, pattern_id) DO UPDATE SET box = EXCLUDED.box, due_date = EXCLUDED.due_date,
               reviews = EXCLUDED.reviews, last_outcome = EXCLUDED.last_outcome""",
        (learner_id, p.pattern, p.box, p.due, p.reviews, p.last_outcome.value),
    )
