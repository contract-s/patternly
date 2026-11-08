"""Schema for hand-written content: patterns, scenarios, and labeled learner answers."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

SLUG = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class Strict(BaseModel):
    """Reject unknown keys so typos in YAML don't pass silently."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Pattern(Strict):
    id: str = Field(pattern=SLUG)
    name: str = Field(min_length=1)
    # Other names for the pattern. The leak checker treats these like the name.
    aliases: list[str] = []


class RubricItem(Strict):
    id: str = Field(pattern=SLUG)
    idea: str = Field(min_length=1)


class Scenario(Strict):
    id: str = Field(pattern=SLUG)
    pattern: str = Field(pattern=SLUG)
    title: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    rubric: list[RubricItem] = Field(min_length=1)
    reference_solution: str = Field(min_length=1)
    time_complexity: str = Field(min_length=1)
    space_complexity: str = Field(min_length=1)

    @field_validator("rubric")
    @classmethod
    def unique_rubric_ids(cls, items: list[RubricItem]) -> list[RubricItem]:
        ids = [item.id for item in items]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate rubric ids: {', '.join(dupes)}")
        return items

    @property
    def rubric_ids(self) -> list[str]:
        return [item.id for item in self.rubric]


class AnswerKind(StrEnum):
    """The six answer types the plan asks for per scenario."""

    CORRECT = "correct"
    PARTIAL = "partial"
    MISSING_KEY_IDEA = "missing_key_idea"
    WRONG_PATTERN = "wrong_pattern"
    VAGUE = "vague"
    ALTERNATIVE = "alternative"


class Verdict(StrEnum):
    """Whether the answer should earn the reveal. Drives the false-pass rate."""

    PASS = "pass"
    FAIL = "fail"


class Label(StrEnum):
    HIT = "hit"
    MISS = "miss"


class Answer(Strict):
    id: str = Field(pattern=SLUG)
    kind: AnswerKind
    verdict: Verdict
    text: str = Field(min_length=1)
    # rubric item id -> hit/miss. Every rubric item must be labeled.
    labels: dict[str, Label]
    notes: str | None = None


class AnswerSet(Strict):
    scenario: str = Field(pattern=SLUG)
    answers: list[Answer] = Field(min_length=1)

    @field_validator("answers")
    @classmethod
    def unique_answer_ids(cls, answers: list[Answer]) -> list[Answer]:
        ids = [a.id for a in answers]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate answer ids: {', '.join(dupes)}")
        return answers


class Split(Strict):
    """Which answers are sealed. Sealed answers are only for final reported metrics."""

    seed: int
    created: str
    # Global answer ids: "<scenario-id>/<answer-id>"
    sealed: list[str]


def answer_key(scenario_id: str, answer_id: str) -> str:
    return f"{scenario_id}/{answer_id}"
