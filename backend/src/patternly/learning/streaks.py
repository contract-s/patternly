"""Streaks: days in a row with a finished lesson, counted in the learner's own time zone.

A missed day breaks the streak unless a streak freeze covers it. Every 7 lessons in a row earns a
freeze, and at most 2 can be banked. Freezes are used up automatically, one per missed day; a gap
longer than the banked freezes resets the streak. Today doesn't count as missed until it's over.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

FREEZE_EVERY = 7
MAX_FREEZES = 2


@dataclass(frozen=True)
class Streak:
    current: int
    longest: int
    freezes: int
    done_today: bool


def compute_streak(done: set[date], today: date) -> Streak:
    if not done:
        return Streak(0, 0, 0, False)
    run = longest = freezes = gap = 0
    day = min(done)
    while day <= today:
        if day in done:
            if gap:
                if gap <= freezes:
                    freezes -= gap
                else:
                    run, freezes = 0, 0
                gap = 0
            run += 1
            longest = max(longest, run)
            if run % FREEZE_EVERY == 0:
                freezes = min(freezes + 1, MAX_FREEZES)
        elif day < today:
            gap += 1
        day += timedelta(days=1)
    if gap > freezes:
        return Streak(0, longest, 0, today in done)
    return Streak(run, longest, freezes - gap, today in done)
