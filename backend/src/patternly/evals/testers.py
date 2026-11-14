"""Tester-trial metrics from the database: hints to solve, daily completion, and longest streak.

Definitions (also in the README):
- Trial window: `days` local days from `start`, only counting days that are over in every time zone, so a day
  still in progress somewhere never counts as missed.
- Daily completion: tester-days with a finished lesson (passed or revealed) / (testers x days in the window).
  Every tester counts from `start`, so pick the day everyone had an account.
- Hints to solve: for each passed lesson, the hints shown before the pass (one per failed attempt). Lessons
  revealed after the last failed attempt are counted separately, since they were never solved.
- Longest streak: each tester's longest run of consecutive finished days inside the window (no freezes), then
  the median across testers.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from psycopg import AsyncConnection


@dataclass(frozen=True)
class LessonRow:
    learner_id: int
    local_date: date
    status: str  # open, passed, revealed
    hints: int  # attempts that showed a hint (failed attempts)


@dataclass(frozen=True)
class TesterStats:
    learner_id: int
    days_finished: int
    longest_streak: int
    passed: int
    revealed: int
    hints_to_solve: list[int]


def last_complete_day(now: datetime) -> date:
    """The latest date that has ended in every time zone (the last zone is UTC-12)."""
    return (now.astimezone(UTC) - timedelta(hours=12)).date() - timedelta(days=1)


def window(start: date, days: int, today: date) -> list[date]:
    """The trial's local days before `today`."""
    return [d for d in (start + timedelta(i) for i in range(days)) if d < today]


def longest_run(finished: set[date], days: list[date]) -> int:
    run = best = 0
    for d in days:
        run = run + 1 if d in finished else 0
        best = max(best, run)
    return best


def tester_stats(learner_id: int, lessons: list[LessonRow], days: list[date]) -> TesterStats:
    inside = [x for x in lessons if x.learner_id == learner_id and x.local_date in set(days)]
    finished = {x.local_date for x in inside if x.status != "open"}
    passed = [x for x in inside if x.status == "passed"]
    return TesterStats(
        learner_id=learner_id,
        days_finished=len(finished),
        longest_streak=longest_run(finished, days),
        passed=len(passed),
        revealed=sum(x.status == "revealed" for x in inside),
        hints_to_solve=[x.hints for x in passed],
    )


def report(learner_ids: list[int], lessons: list[LessonRow], start: date, days: int, today: date) -> dict:
    span = window(start, days, today)
    testers = [tester_stats(i, lessons, span) for i in learner_ids]
    hints = [h for t in testers for h in t.hints_to_solve]
    tester_days = len(testers) * len(span)
    finished_days = sum(t.days_finished for t in testers)
    return {
        "start": start,
        "days": len(span),
        "testers": testers,
        "tester_days": tester_days,
        "finished_days": finished_days,
        "completion": finished_days / tester_days if tester_days else None,
        "passed": len(hints),
        "revealed": sum(t.revealed for t in testers),
        "mean_hints_to_solve": statistics.mean(hints) if hints else None,
        "first_try": sum(h == 0 for h in hints),
        "median_longest_streak": statistics.median([t.longest_streak for t in testers]) if testers else None,
    }


def format_report(r: dict) -> str:
    def pct(x):
        return "no data" if x is None else f"{x:.1%}"

    def num(x, fmt="{:.2f}"):
        return "no data" if x is None else fmt.format(x)

    end = r["start"] + timedelta(r["days"] - 1) if r["days"] else None
    lines = [
        f"Window: {r['start']} to {end} ({r['days']} complete days), {len(r['testers'])} testers",
        f"Daily completion: {pct(r['completion'])} ({r['finished_days']} of {r['tester_days']} tester-days)",
        (
            f"Hints to solve: {num(r['mean_hints_to_solve'])} on average over {r['passed']} solved lessons "
            f"({r['first_try']} solved with no hint)"
            if r["passed"]
            else "Hints to solve: no solved lessons yet"
        )
        + f"; {r['revealed']} revealed unsolved",
        f"Longest streak: median {num(r['median_longest_streak'], '{:g}')} days",
        "",
        f"{'learner':>8} {'days':>5} {'streak':>7} {'passed':>7} {'revealed':>9} {'hints/solve':>12}",
    ]
    for t in r["testers"]:
        mean = num(statistics.mean(t.hints_to_solve)) if t.hints_to_solve else "-"
        lines.append(
            f"{t.learner_id:>8} {t.days_finished:>5} {t.longest_streak:>7} {t.passed:>7} {t.revealed:>9} {mean:>12}"
        )
    return "\n".join(lines)


async def load(
    conn: AsyncConnection, start: date, days: int, exclude: list[str] = (), only: list[int] = ()
) -> tuple[list[int], list[LessonRow]]:
    """Testers (every learner, minus excluded emails, or just `only`) and their lessons in the window."""
    cur = await conn.execute(
        """SELECT id FROM learners
           WHERE NOT (lower(email) = ANY(%s)) AND (cardinality(%s::bigint[]) = 0 OR id = ANY(%s))
           ORDER BY id""",
        ([e.lower() for e in exclude], list(only), list(only)),
    )
    ids = [r[0] for r in await cur.fetchall()]
    cur = await conn.execute(
        """SELECT l.learner_id, l.local_date, l.status, count(a.id) FILTER (WHERE a.verdict = 'fail')
           FROM lessons l LEFT JOIN attempts a ON a.lesson_id = l.id
           WHERE l.learner_id = ANY(%s) AND l.local_date >= %s AND l.local_date < %s
           GROUP BY l.id ORDER BY l.learner_id, l.local_date""",
        (ids, start, start + timedelta(days)),
    )
    return ids, [LessonRow(*r) for r in await cur.fetchall()]
