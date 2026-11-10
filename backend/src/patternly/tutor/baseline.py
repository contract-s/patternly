"""Weekend 2 baseline tutor: one prompt with the scenario, rubric, and answer; structured output back.

Deliberately simple. No tools, no leak checker. It's the number later weekends have to beat.
Weekend 3 adds one option: pass retrieved pattern notes and they go into the prompt as reference.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, Field, create_model

from ..content.models import Scenario

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "medium"
MAX_TOKENS = 16_000

# USD per million tokens (input, output). Output includes thinking tokens.
PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

SYSTEM_PROMPT = """\
You grade a learner's plain-words explanation of how they would solve an algorithm scenario.

You get the scenario, a hidden rubric of key ideas, and the learner's explanation. For every rubric
item, decide whether the explanation clearly states that idea.

Grading rules:
- Mark an item as hit only if the explanation actually says it, in any wording. Naming a technique
  or using the right buzzword without the idea itself is not a hit. Vague gestures ("do it
  efficiently", "keep track of things") are not hits.
- Judge each item on its own. A mistake elsewhere doesn't cancel an item the learner did state,
  but if the explanation states an item incorrectly, it's a miss.
- For evidence, quote or closely paraphrase the part of the explanation that supports the call,
  or say what's missing.

Verdict:
- pass: the explanation describes a correct solution to the scenario. A different approach that
  is also correct and efficient enough for the scenario can pass even if it misses rubric items
  that are specific to the expected approach.
- fail: anything else, including explanations that are vague, incomplete, wrong, or that would
  give wrong results on some inputs.

Hint:
- If the verdict is fail, write one short hint that nudges the learner toward the most important
  thing they missed or got wrong. Ask a question or point at what to notice. Don't name the
  algorithm or pattern, don't give the full solution, and don't mention the rubric.
- If the verdict is pass, the hint is an empty string.
"""


NOTES_PROMPT = """
Reference notes:
- You may also get reference notes about algorithm patterns, found by searching for the learner's
  explanation. They may or may not describe the approach this scenario expects.
- Use them to recognize correct ideas stated in unfamiliar words and to spot the common mistakes
  they list. Grade against the rubric, not against the notes.
- The notes name patterns. Never put a pattern name or alias from the notes in your hint.
"""


class ItemCall(BaseModel):
    rubric_id: str
    evidence: str
    hit: bool


class Grade(BaseModel):
    """The grader's result, normalized: one call per rubric item, in rubric order."""

    items: list[ItemCall]
    verdict: Literal["pass", "fail"]
    hint: str


class ItemVerdict(BaseModel):
    evidence: str = Field(description="Quote or paraphrase supporting the call, or what's missing.")
    hit: bool


def _field_name(rubric_id: str) -> str:
    # Rubric ids are slugs like "shrink-left"; schema field names must be identifiers.
    return "item_" + rubric_id.replace("-", "_")


_output_models: dict[tuple[str, ...], type[BaseModel]] = {}


def output_model(scenario: Scenario) -> type[BaseModel]:
    """A response schema with one required field per rubric item, so the model can't skip or
    repeat an item."""
    ids = tuple(scenario.rubric_ids)
    if ids not in _output_models:
        fields = {
            _field_name(item.id): (ItemVerdict, Field(description=f"Rubric item '{item.id}': {item.idea}"))
            for item in scenario.rubric
        }
        items_model = create_model("RubricCalls", **fields)
        _output_models[ids] = create_model(
            "GradeOutput",
            items=(items_model, Field(description="One call per rubric item.")),
            verdict=(Literal["pass", "fail"], ...),
            hint=(str, ...),
        )
    return _output_models[ids]


def to_grade(output: BaseModel, scenario: Scenario) -> Grade:
    calls = []
    for item in scenario.rubric:
        v = getattr(output.items, _field_name(item.id))
        calls.append(ItemCall(rubric_id=item.id, evidence=v.evidence, hit=v.hit))
    return Grade(items=calls, verdict=output.verdict, hint=output.hint)


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
    latency_s: float
    model: str

    @property
    def cost_usd(self) -> float:
        price_in, price_out = PRICES.get(self.model, (0.0, 0.0))
        return (self.input_tokens * price_in + self.output_tokens * price_out) / 1_000_000


class GradeError(Exception):
    """The model's output couldn't be used (refusal, truncation, or wrong rubric ids)."""

    def __init__(self, message: str, usage: Usage | None = None) -> None:
        super().__init__(message)
        self.usage = usage


class MessagesClient(Protocol):
    """The slice of anthropic.Anthropic this module uses (makes testing without the API easy)."""

    @property
    def messages(self): ...


def build_user_message(scenario: Scenario, answer_text: str, notes: list[str] | None = None) -> str:
    # The pattern name and reference solution are left out on purpose: the grader should judge
    # against the rubric, and can't leak a name it was never given.
    rubric = "\n".join(f"- {item.id}: {item.idea}" for item in scenario.rubric)
    reference = ""
    if notes:
        reference = "".join(f"<note>\n{n.strip()}\n</note>\n" for n in notes)
        reference = f"<reference_notes>\n{reference}</reference_notes>\n\n"
    return reference + (
        f"<scenario>\n{scenario.title}\n\n{scenario.prompt.strip()}\n</scenario>\n\n"
        f"<rubric>\n{rubric}\n</rubric>\n\n"
        f"<learner_explanation>\n{answer_text.strip()}\n</learner_explanation>"
    )


def check_grade(grade: Grade, scenario: Scenario) -> Grade:
    """Require exactly one call per rubric item, and return them in rubric order."""
    by_id: dict[str, ItemCall] = {}
    for call in grade.items:
        if call.rubric_id in by_id:
            raise GradeError(f"duplicate call for rubric item '{call.rubric_id}'")
        by_id[call.rubric_id] = call
    expected = scenario.rubric_ids
    missing = [r for r in expected if r not in by_id]
    extra = sorted(set(by_id) - set(expected))
    if missing or extra:
        raise GradeError(f"rubric ids don't match (missing: {missing}, unexpected: {extra})")
    return grade.model_copy(update={"items": [by_id[r] for r in expected]})


def grade_answer(
    client: MessagesClient,
    scenario: Scenario,
    answer_text: str,
    *,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    notes: list[str] | None = None,
) -> tuple[Grade, Usage]:
    started = time.perf_counter()
    response = client.messages.parse(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT + NOTES_PROMPT if notes else SYSTEM_PROMPT,
        output_config={"effort": effort},
        output_format=output_model(scenario),
        messages=[{"role": "user", "content": build_user_message(scenario, answer_text, notes)}],
    )
    usage = Usage(
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        latency_s=time.perf_counter() - started,
        model=model,
    )
    if response.stop_reason != "end_turn":
        raise GradeError(f"stopped with '{response.stop_reason}'", usage)
    if response.parsed_output is None:
        raise GradeError("no parsed output", usage)
    try:
        return check_grade(to_grade(response.parsed_output, scenario), scenario), usage
    except GradeError as e:
        raise GradeError(str(e), usage) from None
