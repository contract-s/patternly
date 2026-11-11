"""Leak checker for hints: does a hint give away more than the learner has earned?

Three checks:
- pattern name: the hint names the scenario's pattern (or an alias) and the learner hadn't written it.
- copied solution: the hint copies a long run of words from the reference solution.
- revealed steps (optional, uses a model): the hint states missed rubric ideas outright, more than its
  hint level allows.

What each hint level may reveal, modeled on the hand-written hint ladders in the scenarios:
- level 1 (nudge): no missed idea stated outright. Questions and "look at X" only.
- level 2 (shape): at most one missed idea stated outright.
- level 3 (strong clue): may state missed ideas, but not all of them when two or more are missing, so the
  learner still has something to work out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel, Field, create_model

from ..content.models import Pattern, RubricItem, Scenario

COPY_RUN_WORDS = 8  # this many consecutive words copied from the reference solution counts as a leak
HINT_LEVELS = (1, 2, 3)


def mentions(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase.lower())}\b", text.lower()) is not None


def names_pattern(pattern: Pattern | None, hint: str, learner_text: str = "") -> str | None:
    """The pattern name or alias the hint uses that the learner hadn't already written, if any.

    Echoing the learner's own words ("is that what your heap puts on top?") gives nothing away.
    """
    if pattern is None or not hint:
        return None
    for phrase in (pattern.name, *pattern.aliases):
        if mentions(hint, phrase) and not mentions(learner_text, phrase):
            return phrase
    return None


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def copied_run(hint: str, source: str, min_words: int = COPY_RUN_WORDS) -> str | None:
    """The first run of at least `min_words` consecutive words the hint shares with `source`, if any."""
    h, s = _words(hint), _words(source)
    if len(h) < min_words or len(s) < min_words:
        return None
    grams = {tuple(s[i : i + min_words]) for i in range(len(s) - min_words + 1)}
    for i in range(len(h) - min_words + 1):
        if tuple(h[i : i + min_words]) in grams:
            return " ".join(h[i : i + min_words])
    return None


def allowed_reveals(level: int, missed: int) -> int:
    """How many missed rubric ideas a hint at this level may state outright."""
    if level == 1:
        return 0
    if level == 2:
        return min(1, missed)
    if level == 3:
        return missed - 1 if missed >= 2 else missed
    raise ValueError(f"hint level must be 1, 2, or 3, not {level}")


@dataclass(frozen=True)
class Leak:
    kind: str  # "pattern-name", "copied-solution", or "revealed-steps"
    detail: str


@dataclass
class LeakReport:
    leaks: list[Leak] = field(default_factory=list)
    judged: bool = False  # whether the revealed-steps check ran
    revealed: list[str] = field(default_factory=list)  # rubric ids the judge said the hint states outright
    usage: object | None = None  # the judge call's Usage, if any

    @property
    def leaky(self) -> bool:
        return bool(self.leaks)

    def feedback(self) -> str:
        """Why the hint was rejected, phrased for the tutor model that has to rewrite it."""
        return "; ".join(f"{leak.kind}: {leak.detail}" for leak in self.leaks)


class Judge(Protocol):
    def revealed(self, scenario: Scenario, missed: list[RubricItem], hint: str) -> tuple[list[str], object]:
        """Rubric ids (from `missed`) the hint states outright, and the call's usage."""
        ...


@dataclass
class LeakChecker:
    patterns: dict[str, Pattern]
    judge: Judge | None = None

    def check(
        self,
        hint: str,
        *,
        scenario: Scenario,
        level: int,
        learner_text: str = "",
        missed: list[str] | None = None,
    ) -> LeakReport:
        """Check one hint. `missed` is the rubric ids the learner hasn't stated (default: all of them)."""
        report = LeakReport()
        if not hint.strip():
            return report
        phrase = names_pattern(self.patterns.get(scenario.pattern), hint, learner_text)
        if phrase:
            report.leaks.append(Leak("pattern-name", f"the hint names the pattern ('{phrase}')"))
        run = copied_run(hint, scenario.reference_solution)
        if run:
            report.leaks.append(Leak("copied-solution", f"the hint copies the reference solution ('{run}')"))
        if self.judge is not None:
            missed_ids = scenario.rubric_ids if missed is None else missed
            missed_items = [item for item in scenario.rubric if item.id in missed_ids]
            if missed_items:
                revealed, usage = self.judge.revealed(scenario, missed_items, hint)
                report.judged, report.revealed, report.usage = True, revealed, usage
                cap = allowed_reveals(level, len(missed_items))
                if len(revealed) > cap:
                    report.leaks.append(
                        Leak(
                            "revealed-steps",
                            f"a level-{level} hint may state {cap} missed idea(s) outright, but this one states "
                            f"{len(revealed)} ({', '.join(revealed)})",
                        )
                    )
        return report


JUDGE_PROMPT = """\
You check hints written for a learner who is explaining how they'd solve an algorithm scenario.

You get the scenario, the key ideas the learner has not stated yet, and a hint. For each key idea,
decide whether the hint states it outright.

A hint states an idea outright when a learner could write that idea down from the hint alone,
without working anything out: the hint says the step, the quantity to keep, the rule, or the
formula. A hint does not state an idea when it only asks a question about it, points at what to
look at, or describes the goal without saying how to reach it.

Judge each idea on its own, and give a one-sentence reason.
"""

DEFAULT_JUDGE_MODEL = "claude-haiku-5-5"
JUDGE_MAX_TOKENS = 4_000


class RevealCall(BaseModel):
    reason: str = Field(description="One sentence: what in the hint states the idea, or why it doesn't.")
    states_outright: bool


def _judge_model(missed: list[RubricItem]) -> type[BaseModel]:
    fields = {
        "idea_" + item.id.replace("-", "_"): (RevealCall, Field(description=f"Key idea '{item.id}': {item.idea}"))
        for item in missed
    }
    return create_model("RevealCalls", **fields)


@dataclass
class ModelJudge:
    """Asks a (cheap) model which missed ideas a hint states outright."""

    client: object
    model: str = DEFAULT_JUDGE_MODEL

    def revealed(self, scenario: Scenario, missed: list[RubricItem], hint: str) -> tuple[list[str], object]:
        import time

        from .baseline import Usage

        ideas = "\n".join(f"- {item.id}: {item.idea}" for item in missed)
        content = (
            f"<scenario>\n{scenario.title}\n\n{scenario.prompt.strip()}\n</scenario>\n\n"
            f"<ideas_not_yet_stated>\n{ideas}\n</ideas_not_yet_stated>\n\n<hint>\n{hint.strip()}\n</hint>"
        )
        started = time.perf_counter()
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=JUDGE_MAX_TOKENS,
            system=JUDGE_PROMPT,
            messages=[{"role": "user", "content": content}],
            output_format=_judge_model(missed),
        )
        usage = Usage.from_response(response.usage, self.model, time.perf_counter() - started)
        parsed = response.parsed_output
        if response.stop_reason != "end_turn" or parsed is None:
            raise RuntimeError(f"leak judge stopped with '{response.stop_reason}'")
        out = [item.id for item in missed if getattr(parsed, "idea_" + item.id.replace("-", "_")).states_outright]
        return out, usage


__all__ = [
    "HINT_LEVELS",
    "Judge",
    "Leak",
    "LeakChecker",
    "LeakReport",
    "ModelJudge",
    "allowed_reveals",
    "copied_run",
    "mentions",
    "names_pattern",
]
