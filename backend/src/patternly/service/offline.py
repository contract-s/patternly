"""An offline grader for trying the app without API calls. Not a real tutor.

A rubric item counts as hit when the answer contains at least half of the item's longer words
(compared on their first 5 letters, so "shrink" matches "shrinks"). The
attempt passes when every item is hit. Hints are the scenario's hand-written hints for the level.
"""

from __future__ import annotations

import re

from ..content.models import Scenario
from ..tutor.agent import AttemptResult
from ..tutor.baseline import ItemCall
from ..tutor.history import History, next_hint_level

MIN_WORD = 5


def _words(text: str) -> set[str]:
    return {w[:MIN_WORD] for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= MIN_WORD}


def offline_grader(scenario: Scenario, answer: str, history: History, learner_id: str) -> AttemptResult:
    previous = history.attempts(learner_id, scenario.id)
    said = _words(answer)
    items = []
    for item in scenario.rubric:
        needed = _words(item.idea)
        hit = bool(needed) and len(needed & said) * 2 >= len(needed)
        items.append(ItemCall(rubric_id=item.id, evidence="offline word match", hit=hit))
    passed = all(c.hit for c in items)
    level = None if passed else next_hint_level(previous)
    return AttemptResult(
        scenario_id=scenario.id,
        learner_id=learner_id,
        attempt=len(previous) + 1,
        hint_level=level,
        items=items,
        verdict="pass" if passed else "fail",
        hint="" if passed else scenario.hints[level - 1],
        hint_source="" if passed else "fallback",
    )
