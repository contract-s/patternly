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

# USD per million tokens: (input, output, cache read). Output includes thinking tokens.
# Cache writes (5-minute TTL) cost 1.25x input. The Batch API halves everything.
PRICES: dict[str, tuple[float, float, float]] = {
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),  # cache read assumed at 0.1x input; check the pricing page
}
CACHE_WRITE_MULTIPLIER = 1.25
BATCH_DISCOUNT = 0.5

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
    input_tokens: int  # uncached input only, as the API reports it
    output_tokens: int
    latency_s: float | None  # None for batch requests
    model: str
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    batch: bool = False

    @property
    def total_input_tokens(self) -> int:
        return self.input_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens

    @property
    def cost_usd(self) -> float:
        price_in, price_out, price_read = PRICES.get(self.model, (0.0, 0.0, 0.0))
        cost = (
            self.input_tokens * price_in
            + self.cache_creation_input_tokens * price_in * CACHE_WRITE_MULTIPLIER
            + self.cache_read_input_tokens * price_read
            + self.output_tokens * price_out
        ) / 1_000_000
        return cost * BATCH_DISCOUNT if self.batch else cost

    @classmethod
    def from_response(cls, usage, model: str, latency_s: float | None, batch: bool = False) -> Usage:
        return cls(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_s=latency_s,
            model=model,
            cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", None) or 0,
            cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", None) or 0,
            batch=batch,
        )


class GradeError(Exception):
    """The model's output couldn't be used (refusal, truncation, or wrong rubric ids)."""

    def __init__(self, message: str, usage: Usage | None = None) -> None:
        super().__init__(message)
        self.usage = usage


class MessagesClient(Protocol):
    """The slice of anthropic.Anthropic this module uses (makes testing without the API easy)."""

    @property
    def messages(self): ...


def build_user_content(scenario: Scenario, answer_text: str, notes: list[str] | None = None) -> list[dict]:
    """Two text blocks: the part shared by every answer to this scenario (cached), then the per-answer part.

    The pattern name and reference solution are left out on purpose: the grader should judge against
    the rubric, and can't leak a name it was never given.
    """
    rubric = "\n".join(f"- {item.id}: {item.idea}" for item in scenario.rubric)
    shared = (
        f"<scenario>\n{scenario.title}\n\n{scenario.prompt.strip()}\n</scenario>\n\n<rubric>\n{rubric}\n</rubric>\n\n"
    )
    reference = ""
    if notes:
        reference = "".join(f"<note>\n{n.strip()}\n</note>\n" for n in notes)
        reference = f"<reference_notes>\n{reference}</reference_notes>\n\n"
    per_answer = f"{reference}<learner_explanation>\n{answer_text.strip()}\n</learner_explanation>"
    return [
        # Everything up to and including this block (system prompt, schema, scenario, rubric) is cached.
        {"type": "text", "text": shared, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": per_answer},
    ]


def build_user_message(scenario: Scenario, answer_text: str, notes: list[str] | None = None) -> str:
    """The user message as plain text (for reading and tests)."""
    return "".join(b["text"] for b in build_user_content(scenario, answer_text, notes))


def request_params(
    scenario: Scenario, answer_text: str, *, model: str, effort: str, notes: list[str] | None = None
) -> dict:
    """Request fields shared by live and batch calls (everything except the output schema)."""
    return {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT + NOTES_PROMPT if notes else SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": build_user_content(scenario, answer_text, notes)}],
    }


def batch_params(
    scenario: Scenario, answer_text: str, *, model: str, effort: str, notes: list[str] | None = None
) -> dict:
    """Params for a Message Batches request. Batches can't use `parse`, so the schema goes in
    `output_config.format` directly, transformed the same way `parse` does it."""
    from anthropic import transform_schema

    schema = transform_schema(output_model(scenario).model_json_schema())
    return {
        **request_params(scenario, answer_text, model=model, effort=effort, notes=notes),
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    }


def finish_grade(scenario: Scenario, stop_reason: str | None, parsed: BaseModel | None, usage: Usage) -> Grade:
    if stop_reason != "end_turn":
        raise GradeError(f"stopped with '{stop_reason}'", usage)
    if parsed is None:
        raise GradeError("no parsed output", usage)
    try:
        return check_grade(to_grade(parsed, scenario), scenario)
    except GradeError as e:
        raise GradeError(str(e), usage) from None


def grade_batch_message(scenario: Scenario, message, model: str) -> tuple[Grade, Usage]:
    """Turn a succeeded batch result's message into a grade."""
    usage = Usage.from_response(message.usage, model, None, batch=True)
    parsed = None
    if message.stop_reason == "end_turn":
        text = next((b.text for b in message.content if b.type == "text"), "")
        try:
            parsed = output_model(scenario).model_validate_json(text)
        except ValueError as e:
            raise GradeError(f"output didn't match the schema: {e}", usage) from None
    return finish_grade(scenario, message.stop_reason, parsed, usage), usage


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
        **request_params(scenario, answer_text, model=model, effort=effort, notes=notes),
        output_config={"effort": effort},
        output_format=output_model(scenario),
    )
    usage = Usage.from_response(response.usage, model, time.perf_counter() - started)
    return finish_grade(scenario, response.stop_reason, response.parsed_output, usage), usage
