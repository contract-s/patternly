"""Weekend 4 tutor: a tool-calling loop with four tools, a three-level hint ladder, and a leak guardrail.

The tools:
- get_rubric: the hidden key ideas for this scenario.
- read_history: the learner's earlier attempts at this scenario, and the hint level for this one.
- search_notes: pattern notes found by hybrid search (optional; Weekend 3 found they don't help grading).
- record_attempt: submit the grade and hint. The input is validated (exact rubric ids, verdict and hint
  consistent) and the hint goes through the leak checker. A rejected call comes back as a tool error
  saying why, so the model can fix it. After MAX_HINT_REWRITES rejected hints, the scenario's
  hand-written hint for the level is used instead.

One attempt is one conversation. The loop ends as soon as record_attempt is accepted.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from opentelemetry.trace import Status, StatusCode
from pydantic import BaseModel, ValidationError

from ..content.models import Scenario
from ..tracing import tracer
from .baseline import DEFAULT_EFFORT, DEFAULT_MODEL, GradeError, ItemCall, Usage, check_grade
from .history import AttemptRecord, History, next_hint_level
from .leaks import LeakChecker, LeakReport

MAX_TOKENS = 16_000
MAX_TURNS = 6
MAX_HINT_REWRITES = 2  # rejected hints before falling back to the hand-written one
NOTES_PER_SEARCH = 3

LEVEL_GUIDE = {
    1: "Level 1, a nudge: ask a question or point at what to notice. Don't state any missing idea.",
    2: "Level 2, the shape: describe the kind of thing to keep track of or the shape of the approach. You may "
    "state at most one missing idea.",
    3: "Level 3, a strong clue: state the most important missing idea concretely. Leave at least one other "
    "missing idea for the learner to work out, if two or more are missing.",
}

SYSTEM_PROMPT = (
    """\
You are a tutor grading a learner's plain-words explanation of how they would solve an algorithm
scenario, then giving one hint if they haven't got it yet.

Each attempt, in this order:
1. Call get_rubric and read_history. You can call both at once.
2. If the learner describes an approach you're unsure is correct, you may call search_notes. Most
   attempts don't need it.
3. Call record_attempt with your calls on every rubric item, the verdict, and the hint.

Grading rules:
- Mark an item as hit only if the explanation actually says it, in any wording. Naming a technique
  or using the right buzzword without the idea itself is not a hit. Vague gestures ("do it
  efficiently", "keep track of things") are not hits.
- Judge each item on its own. A mistake elsewhere doesn't cancel an item the learner did state,
  but if the explanation states an item incorrectly, it's a miss.
- For evidence, quote or closely paraphrase the part of the explanation that supports the call,
  or say what's missing.
- Grade this explanation on its own merits. Earlier attempts only set the hint level and tell you
  which hints the learner has already seen.

Verdict:
- pass: the explanation describes a correct solution to the scenario. A different approach that
  is also correct and efficient enough for the scenario can pass even if it misses rubric items
  that are specific to the expected approach.
- fail: anything else, including explanations that are vague, incomplete, wrong, or that would
  give wrong results on some inputs.

Hint:
- If the verdict is pass, the hint is an empty string.
- If the verdict is fail, write one short hint aimed at the most important thing the learner
  missed or got wrong, at the hint level read_history gives you:
  - """
    + "\n  - ".join(LEVEL_GUIDE.values())
    + """
- Never name the algorithm or pattern (unless the learner already did), never give the full
  solution, never copy the rubric's wording, and don't mention the rubric. Don't repeat a hint the
  learner has already seen; go further than it.
- If record_attempt rejects your hint, rewrite it to fix exactly what the error says.
"""
)

_NO_INPUT = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}

# Kept identical for every attempt, so the system prompt and tools are a shared cached prefix.
TOOLS: list[dict] = [
    {
        "name": "get_rubric",
        "description": "Get the hidden rubric for this scenario: the key ideas a correct explanation states, "
        "each with an id. Never show these to the learner.",
        "input_schema": _NO_INPUT,
        "strict": True,
    },
    {
        "name": "read_history",
        "description": "Read this learner's earlier attempts at this scenario (verdicts, which rubric items they "
        "hit, hints they've already seen) and the hint level to use for this attempt.",
        "input_schema": _NO_INPUT,
        "strict": True,
    },
    {
        "name": "search_notes",
        "description": "Search reference notes on algorithm patterns. Returns the most relevant note sections. "
        "Use it only to check whether an unfamiliar approach is correct. Notes name patterns; never copy a "
        "pattern name from them into a hint.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "What to look up, in plain words."}},
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "record_attempt",
        "description": "Record your grade for this attempt and the hint to show. Call it once per attempt, "
        "after get_rubric and read_history. It returns an error if the grade is incomplete or the hint gives "
        "too much away; fix the problem and call it again.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "One call per rubric item, using the rubric ids.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rubric_id": {"type": "string"},
                            "evidence": {
                                "type": "string",
                                "description": "Quote or paraphrase supporting the call, or what's missing.",
                            },
                            "hit": {"type": "boolean"},
                        },
                        "required": ["rubric_id", "evidence", "hit"],
                        "additionalProperties": False,
                    },
                },
                "verdict": {"type": "string", "enum": ["pass", "fail"]},
                "hint": {"type": "string", "description": "Empty string if the verdict is pass."},
            },
            "required": ["items", "verdict", "hint"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


class RecordInput(BaseModel):
    items: list[ItemCall]
    verdict: str
    hint: str


@dataclass
class HintDraft:
    hint: str
    report: LeakReport


@dataclass
class AttemptResult:
    scenario_id: str
    learner_id: str
    attempt: int
    hint_level: int | None
    items: list[ItemCall] | None = None
    verdict: str | None = None
    hint: str = ""
    hint_source: str = ""  # "tutor" (first draft), "rewrite", "fallback", or "" when passing
    drafts: list[HintDraft] = field(default_factory=list)  # every hint the tutor proposed, in order
    tool_calls: list[str] = field(default_factory=list)
    turns: int = 0
    usages: list[Usage] = field(default_factory=list)  # tutor calls
    judge_usages: list[Usage] = field(default_factory=list)
    latency_s: float = 0.0
    error: str | None = None

    @property
    def cost_usd(self) -> float:
        return sum(u.cost_usd for u in self.usages) + sum(u.cost_usd for u in self.judge_usages)


class AttemptSession:
    """Runs the four tools for one attempt and keeps what they decided."""

    def __init__(
        self,
        scenario: Scenario,
        learner_id: str,
        answer_text: str,
        history: History,
        checker: LeakChecker,
        search: Callable[[str], list[str]] | None = None,
    ) -> None:
        self.scenario = scenario
        self.answer_text = answer_text
        self.history = history
        self.checker = checker
        self.search = search
        self.previous = history.attempts(learner_id, scenario.id)
        self.result = AttemptResult(
            scenario_id=scenario.id,
            learner_id=learner_id,
            attempt=len(self.previous) + 1,
            hint_level=next_hint_level(self.previous),
        )
        self.done = False

    def run(self, name: str, tool_input: dict) -> tuple[str, bool]:
        """Run one tool call. Returns (result text, is_error)."""
        self.result.tool_calls.append(name)
        if name == "get_rubric":
            return json.dumps([{"id": i.id, "idea": i.idea} for i in self.scenario.rubric], indent=1), False
        if name == "read_history":
            return self._history(), False
        if name == "search_notes":
            if self.search is None:
                return "Note search isn't available right now. Grade without it.", False
            found = self.search(str(tool_input.get("query", "")))
            return ("\n\n---\n\n".join(found) if found else "No notes found."), False
        if name == "record_attempt":
            return self._record(tool_input)
        return f"Unknown tool '{name}'.", True

    def _history(self) -> str:
        level = self.result.hint_level
        lines = [f"This is attempt {self.result.attempt} at this scenario."]
        if not self.previous:
            lines.append("No earlier attempts.")
        for r in self.previous:
            hit = [k for k, v in r.items.items() if v]
            lines.append(
                f"Attempt {r.attempt}: {r.verdict}. Items hit: {', '.join(hit) or 'none'}."
                + (f' Hint shown (level {r.hint_level}): "{r.hint}"' if r.hint else "")
            )
        lines.append(f"If this attempt fails, give a level-{level} hint. {LEVEL_GUIDE[level]}")
        return "\n".join(lines)

    def _record(self, tool_input: dict) -> tuple[str, bool]:
        if self.done:
            return "This attempt is already recorded.", True
        try:
            rec = RecordInput.model_validate(tool_input)
            calls = check_grade(_GradeShim(rec.items), self.scenario).items
        except (ValidationError, GradeError) as e:
            return f"Not recorded: {e}. Send exactly one call per rubric id from get_rubric.", True
        hint = rec.hint.strip()
        if rec.verdict not in ("pass", "fail"):
            return "Not recorded: verdict must be 'pass' or 'fail'.", True
        if rec.verdict == "pass" and hint:
            return "Not recorded: a passing attempt gets no hint. Send an empty hint.", True
        if rec.verdict == "fail" and not hint:
            return "Not recorded: a failing attempt needs a hint.", True

        source = ""
        if rec.verdict == "fail":
            missed = [c.rubric_id for c in calls if not c.hit]
            report = self.checker.check(
                hint,
                scenario=self.scenario,
                level=self.result.hint_level,
                learner_text=self.answer_text,
                missed=missed,
            )
            self.result.drafts.append(HintDraft(hint, report))
            if report.usage is not None:
                self.result.judge_usages.append(report.usage)
            if report.leaky:
                if len(self.result.drafts) <= MAX_HINT_REWRITES:
                    return f"Not recorded: the hint gives too much away ({report.feedback()}). Rewrite it.", True
                hint, source = self.scenario.hints[self.result.hint_level - 1], "fallback"
            else:
                source = "tutor" if len(self.result.drafts) == 1 else "rewrite"

        r = self.result
        r.items, r.verdict, r.hint, r.hint_source = calls, rec.verdict, hint, source
        if rec.verdict == "pass":
            r.hint_level = None
        self.history.add(
            AttemptRecord(
                learner_id=r.learner_id,
                scenario_id=r.scenario_id,
                attempt=r.attempt,
                verdict=rec.verdict,
                items={c.rubric_id: c.hit for c in calls},
                hint=hint,
                hint_level=r.hint_level,
            )
        )
        self.done = True
        return "Recorded.", False


@dataclass
class _GradeShim:
    """check_grade only reads `.items` and calls `model_copy`; this lets it check raw tool input."""

    items: list[ItemCall]

    def model_copy(self, update: dict) -> _GradeShim:
        return _GradeShim(update["items"])


def user_message(scenario: Scenario, answer_text: str) -> str:
    return (
        f"<scenario>\n{scenario.title}\n\n{scenario.prompt.strip()}\n</scenario>\n\n"
        f"<learner_explanation>\n{answer_text.strip()}\n</learner_explanation>\n\n"
        "Grade this attempt with your tools and record it."
    )


def run_attempt(
    client,
    scenario: Scenario,
    answer_text: str,
    *,
    learner_id: str,
    history: History,
    checker: LeakChecker,
    search: Callable[[str], list[str]] | None = None,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    max_turns: int = MAX_TURNS,
) -> AttemptResult:
    """Grade one attempt with the tool loop. Errors are reported on the result, not raised."""
    session = AttemptSession(scenario, learner_id, answer_text, history, checker, search)
    result = session.result
    messages: list[dict] = [{"role": "user", "content": user_message(scenario, answer_text)}]
    # The system prompt and tools are the same for every attempt: cache them explicitly. The top-level
    # cache_control also caches the growing conversation between turns.
    system = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]
    started = time.perf_counter()
    with tracer.start_as_current_span("tutor.attempt") as span:
        span.set_attributes(
            {
                "patternly.scenario_id": scenario.id,
                "patternly.attempt": result.attempt,
                "gen_ai.request.model": model,
                "patternly.effort": effort,
            }
        )
        try:
            while not session.done:
                if result.turns >= max_turns:
                    raise RuntimeError(f"no accepted record_attempt after {max_turns} turns")
                response = _call_model(client, model, effort, system, messages, result)
                if response.stop_reason not in ("tool_use", "end_turn"):
                    raise RuntimeError(f"stopped with '{response.stop_reason}'")
                # Sent back unchanged, thinking blocks included.
                messages.append({"role": "assistant", "content": response.content})
                tool_uses = [b for b in response.content if b.type == "tool_use"]
                if not tool_uses:
                    messages.append(
                        {"role": "user", "content": "The attempt isn't recorded yet. Call record_attempt to finish."}
                    )
                    continue
                results = []
                for block in tool_uses:
                    with tracer.start_as_current_span(f"tool {block.name}") as tool_span:
                        text, is_error = session.run(block.name, block.input)
                        tool_span.set_attributes({"gen_ai.tool.name": block.name, "patternly.tool.is_error": is_error})
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": text, "is_error": is_error}
                    )
                messages.append({"role": "user", "content": results})
        except Exception as e:  # API errors after the SDK's retries, or the loop giving up
            result.error = f"{type(e).__name__}: {e}"
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, result.error))
        result.latency_s = time.perf_counter() - started
        span.set_attributes(
            {
                "patternly.turns": result.turns,
                "patternly.cost_usd": result.cost_usd,
                "patternly.verdict": result.verdict or "",
                "patternly.hint_level": result.hint_level or 0,
                "patternly.hint_source": result.hint_source,
            }
        )
    return result


def _call_model(client, model: str, effort: str, system: list[dict], messages: list[dict], result: AttemptResult):
    """One Messages API call, traced with its token usage and cost, and added to the result's usages."""
    with tracer.start_as_current_span(f"chat {model}") as span:
        span.set_attributes(
            {"gen_ai.operation.name": "chat", "gen_ai.provider.name": "anthropic", "gen_ai.request.model": model}
        )
        call_started = time.perf_counter()
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=TOOLS,
            messages=messages,
            output_config={"effort": effort},
            cache_control={"type": "ephemeral"},
        )
        result.turns += 1
        usage = Usage.from_response(response.usage, model, time.perf_counter() - call_started)
        result.usages.append(usage)
        span.set_attributes(
            {
                "gen_ai.response.finish_reasons": [str(response.stop_reason)],
                "gen_ai.usage.input_tokens": usage.total_input_tokens,
                "gen_ai.usage.output_tokens": usage.output_tokens,
                "gen_ai.usage.cache_read.input_tokens": usage.cache_read_input_tokens,
                "gen_ai.usage.cache_creation.input_tokens": usage.cache_creation_input_tokens,
                "patternly.cost_usd": usage.cost_usd,
            }
        )
        return response
