"""A learner's past attempts. In memory for now; Weekend 5 moves this into Postgres."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from .leaks import HINT_LEVELS


@dataclass(frozen=True)
class AttemptRecord:
    learner_id: str
    scenario_id: str
    attempt: int  # 1-based, per learner and scenario
    verdict: str  # "pass" or "fail"
    items: dict[str, bool]  # rubric id -> hit
    hint: str
    hint_level: int | None  # None when the attempt passed
    at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class History(Protocol):
    def attempts(self, learner_id: str, scenario_id: str) -> list[AttemptRecord]: ...

    def add(self, record: AttemptRecord) -> None: ...


class InMemoryHistory:
    def __init__(self) -> None:
        self._records: list[AttemptRecord] = []

    def attempts(self, learner_id: str, scenario_id: str) -> list[AttemptRecord]:
        return [r for r in self._records if r.learner_id == learner_id and r.scenario_id == scenario_id]

    def add(self, record: AttemptRecord) -> None:
        self._records.append(record)


def next_hint_level(previous: list[AttemptRecord]) -> int:
    """Level 1 on the first failed attempt, then one level stronger per failure, capped at 3."""
    failures = sum(1 for r in previous if r.verdict == "fail")
    return min(failures + 1, HINT_LEVELS[-1])
