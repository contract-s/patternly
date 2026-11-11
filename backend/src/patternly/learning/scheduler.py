"""Leitner-style spaced repetition, one box per pattern.

A pattern moves up a box when the learner solves it without hints, stays put when they need hints,
and drops to box 1 (back tomorrow) when they run out of attempts and the answer is revealed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

INTERVAL_DAYS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}
TOP_BOX = max(INTERVAL_DAYS)


class Outcome(StrEnum):
    CLEAN = "clean"  # passed on the first attempt
    HINTED = "hinted"  # passed after one or more hints
    MISSED = "missed"  # never passed; the pattern was revealed


@dataclass(frozen=True)
class Progress:
    pattern: str
    box: int
    due: date
    reviews: int  # finished lessons on this pattern
    last_outcome: Outcome


def schedule(prev: Progress | None, pattern: str, outcome: Outcome, today: date) -> Progress:
    """The pattern's progress after a lesson on `today` ends with `outcome`."""
    if prev is None:
        box = 2 if outcome == Outcome.CLEAN else 1
    elif outcome == Outcome.CLEAN:
        box = min(prev.box + 1, TOP_BOX)
    elif outcome == Outcome.HINTED:
        box = prev.box
    else:
        box = 1
    reviews = (prev.reviews if prev else 0) + 1
    return Progress(pattern, box, today + timedelta(days=INTERVAL_DAYS[box]), reviews, outcome)
