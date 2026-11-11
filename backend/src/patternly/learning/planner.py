"""Pick today's lesson: an overdue review first, else the next new pattern, else extra practice."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .scheduler import Progress


@dataclass(frozen=True)
class Pick:
    scenario: str
    pattern: str
    kind: str  # "review", "new", or "practice"


def pick_scenario(scenarios: list[str], last_seen: dict[str, date]) -> str:
    """An unseen scenario if there is one (in id order), else the one seen longest ago."""
    unseen = [s for s in sorted(scenarios) if s not in last_seen]
    if unseen:
        return unseen[0]
    return min(sorted(scenarios), key=lambda s: last_seen[s])


def plan(
    today: date,
    curriculum: list[str],
    scenarios_by_pattern: dict[str, list[str]],
    progress: dict[str, Progress],
    last_seen: dict[str, date],
) -> Pick:
    """`curriculum` is the pattern order for new lessons; `last_seen` maps scenario id -> last lesson date."""
    teachable = [p for p in curriculum if scenarios_by_pattern.get(p)]
    if not teachable:
        raise ValueError("no patterns with scenarios")
    due = sorted(
        (p for p in progress.values() if p.due <= today and p.pattern in teachable), key=lambda p: (p.due, p.box)
    )
    if due:
        pattern, kind = due[0].pattern, "review"
    else:
        new = [p for p in teachable if p not in progress]
        if new:
            pattern, kind = new[0], "new"
        else:
            pattern = min(
                (p for p in progress.values() if p.pattern in teachable), key=lambda p: (p.due, p.box)
            ).pattern
            kind = "practice"
    return Pick(pick_scenario(scenarios_by_pattern[pattern], last_seen), pattern, kind)
