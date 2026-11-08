"""Cross-file checks on loaded content, plus the Weekend 1 "done" check."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .loader import ANSWERS_DIR, SCENARIOS_DIR, SPLIT_FILE, Content, Issue
from .models import AnswerKind, Label, Verdict

# Weekend 1 targets from the project plan.
TARGET_PATTERNS = 5
TARGET_SCENARIOS = 10
ANSWERS_PER_SCENARIO = len(AnswerKind)  # one of each kind
TARGET_SEALED = 20


def _mentions(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase.lower())}\b", text.lower()) is not None


def check(content: Content) -> list[Issue]:
    """Return load issues plus cross-reference and consistency issues."""
    issues = list(content.issues)

    for sid, s in sorted(content.scenarios.items()):
        where = f"{SCENARIOS_DIR}/{sid}.yaml"
        pattern = content.patterns.get(s.pattern)
        if pattern is None:
            issues.append(Issue("error", where, f"unknown pattern '{s.pattern}'"))
        else:
            # The learner must not be handed the answer in the scenario text.
            for phrase in (pattern.name, *pattern.aliases):
                if _mentions(s.prompt, phrase) or _mentions(s.title, phrase):
                    issues.append(Issue("warning", where, f"title or prompt names the pattern ('{phrase}')"))
                for n, hint in enumerate(s.hints, start=1):
                    if _mentions(hint, phrase):
                        issues.append(Issue("error", where, f"hint {n} names the pattern ('{phrase}')"))
        if sid not in content.answer_sets:
            issues.append(Issue("warning", where, "no answers file yet"))

    for sid, aset in sorted(content.answer_sets.items()):
        where = f"{ANSWERS_DIR}/{sid}.yaml"
        scenario = content.scenarios.get(sid)
        if scenario is None:
            issues.append(Issue("error", where, f"no scenario with id '{sid}'"))
            continue
        rubric = set(scenario.rubric_ids)
        for a in aset.answers:
            aw = f"{where} [{a.id}]"
            unknown = sorted(set(a.labels) - rubric)
            missing = [r for r in scenario.rubric_ids if r not in a.labels]
            if unknown:
                issues.append(Issue("error", aw, f"labels unknown rubric items: {', '.join(unknown)}"))
            if missing:
                issues.append(Issue("error", aw, f"rubric items not labeled: {', '.join(missing)}"))
            all_hit = all(a.labels.get(r) == Label.HIT for r in scenario.rubric_ids)
            if a.kind == AnswerKind.CORRECT and (a.verdict != Verdict.PASS or not all_hit):
                issues.append(Issue("warning", aw, "kind 'correct' but not a pass with every item hit"))
            if a.kind in (AnswerKind.WRONG_PATTERN, AnswerKind.VAGUE) and a.verdict == Verdict.PASS:
                issues.append(Issue("warning", aw, f"kind '{a.kind}' labeled as a pass"))
            if a.kind == AnswerKind.ALTERNATIVE and a.verdict != Verdict.PASS:
                issues.append(Issue("warning", aw, "kind 'alternative' should be a valid approach (pass)"))

        kinds = Counter(a.kind for a in aset.answers)
        absent = [k.value for k in AnswerKind if kinds[k] == 0]
        if absent:
            issues.append(Issue("warning", where, f"missing answer kinds: {', '.join(absent)}"))

    if content.split is not None:
        known = {la.key for la in content.all_answers()}
        unknown = sorted(set(content.split.sealed) - known)
        if unknown:
            issues.append(Issue("error", SPLIT_FILE, f"sealed ids not found: {', '.join(unknown)}"))
        if len(set(content.split.sealed)) != len(content.split.sealed):
            issues.append(Issue("error", SPLIT_FILE, "sealed list has duplicates"))

    return issues


@dataclass(frozen=True)
class Progress:
    patterns_used: int
    scenarios: int
    labeled_answers: int
    sealed: int
    errors: int

    @property
    def done(self) -> bool:
        return (
            self.errors == 0
            and self.patterns_used >= TARGET_PATTERNS
            and self.scenarios >= TARGET_SCENARIOS
            and self.labeled_answers >= TARGET_SCENARIOS * ANSWERS_PER_SCENARIO
            and self.sealed >= TARGET_SEALED
        )


def weekend1_progress(content: Content, issues: list[Issue]) -> Progress:
    """An answer counts as labeled only when it has no errors of its own."""
    bad = {i.where for i in issues if i.level == "error"}
    labeled = sum(
        1
        for la in content.all_answers()
        if f"{ANSWERS_DIR}/{la.scenario.id}.yaml [{la.answer.id}]" not in bad
    )
    return Progress(
        patterns_used=len({s.pattern for s in content.scenarios.values() if s.pattern in content.patterns}),
        scenarios=len(content.scenarios),
        labeled_answers=labeled,
        sealed=len(content.split.sealed) if content.split else 0,
        errors=sum(1 for i in issues if i.level == "error"),
    )
