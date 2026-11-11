"""Offline tests for the tool-using tutor, the hint ladder, and the leak checker. No API calls."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from patternly.content.loader import load_content
from patternly.content.models import Pattern
from patternly.content.split import write_split
from patternly.evals.agent import AgentEvalConfig, run_agent_eval
from patternly.evals.leaks import PlantedLeak, run_leak_eval, summarize
from patternly.tutor.agent import MAX_HINT_REWRITES, TOOLS, run_attempt
from patternly.tutor.history import AttemptRecord, InMemoryHistory, next_hint_level
from patternly.tutor.leaks import LeakChecker, allowed_reveals, copied_run, names_pattern

from .conftest import answer_set, scenario

USAGE = SimpleNamespace(input_tokens=100, output_tokens=50, cache_read_input_tokens=0, cache_creation_input_tokens=0)


def tool_use(name: str, tool_input: dict, i: int = 0):
    return SimpleNamespace(type="tool_use", id=f"tu_{name}_{i}", name=name, input=tool_input)


def response(*blocks, stop_reason="tool_use"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason, usage=USAGE)


class ScriptedMessages:
    """Replies with a scripted sequence of responses; records every request."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.script.pop(0)


class ScriptedClient:
    def __init__(self, script):
        self.messages = ScriptedMessages(script)


def record(hits: dict[str, bool], verdict: str, hint: str = ""):
    items = [{"rubric_id": k, "evidence": "e", "hit": v} for k, v in hits.items()]
    return tool_use("record_attempt", {"items": items, "verdict": verdict, "hint": hint}, i=len(hint))


@pytest.fixture
def content(content_dir):
    content_dir.patterns([{"id": "p", "name": "Hidden Trick", "aliases": ["HT"]}])
    s = scenario("s1", "p")
    s["reference_solution"] = "Walk the list once and keep a running total of every value seen so far."
    content_dir.scenario(s)
    content_dir.answers(answer_set("s1"))
    return load_content(content_dir.root)


def checker(content, judge=None):
    return LeakChecker(content.patterns, judge)


# ---- leak checks ----


def test_names_pattern_ignores_learner_echo():
    p = Pattern(id="p", name="Hidden Trick", aliases=["HT"])
    assert names_pattern(p, "Try the hidden trick here.") == "Hidden Trick"
    assert names_pattern(p, "Is HT what you meant?") == "HT"
    assert names_pattern(p, "Your hidden trick idea: what does it keep?", "I'd use the hidden trick") is None
    assert names_pattern(p, "What do you keep?") is None


def test_copied_run_needs_eight_words():
    ref = "Walk the list once and keep a running total of every value seen so far."
    assert (
        copied_run("Hint: keep a running total of every value seen.", ref) == "keep a running total of every value seen"
    )
    assert copied_run("Keep a running total of values.", ref) is None


def test_allowed_reveals_by_level():
    assert [allowed_reveals(1, m) for m in (1, 3)] == [0, 0]
    assert [allowed_reveals(2, m) for m in (1, 3)] == [1, 1]
    assert [allowed_reveals(3, m) for m in (1, 2, 4)] == [1, 1, 3]


class FakeJudge:
    def __init__(self, revealed):
        self.revealed_ids = revealed
        self.calls = 0

    def revealed(self, scenario, missed, hint):
        self.calls += 1
        return [i for i in self.revealed_ids if i in {m.id for m in missed}], None


def test_judge_cap_depends_on_level(content):
    s = content.scenarios["s1"]
    judge = FakeJudge(["idea-a"])
    c = checker(content, judge)
    assert c.check("hint", scenario=s, level=1).leaky
    assert not c.check("hint", scenario=s, level=2).leaky
    # Only idea-a missing: a level-3 hint may state it.
    assert not c.check("hint", scenario=s, level=3, missed=["idea-a"]).leaky
    # Nothing missing: the judge isn't asked.
    calls = judge.calls
    assert not c.check("hint", scenario=s, level=1, missed=[]).leaky
    assert judge.calls == calls


def test_leak_eval_counts_planted_and_clean(content):
    planted = [
        PlantedLeak(scenario="s1", level=1, kind="pattern-name", hint="Use the Hidden Trick."),
        PlantedLeak(scenario="s1", level=2, kind="copied-solution", hint="Keep a running total of every value seen."),
        PlantedLeak(scenario="s1", level=1, kind="revealed-steps", hint="States idea a."),
        PlantedLeak(scenario="s1", level=1, kind="none", hint="Hidden trick?", learner_text="the hidden trick"),
    ]
    records = run_leak_eval(content, planted, checker(content))  # no judge: revealed-steps skipped
    s = summarize(records, judged=False)
    assert s["planted_caught"] == s["planted_total"] == 2
    assert s["tricky_flagged"] == 0 and s["tricky_total"] == 1
    assert s["clean_total"] == 3 and s["clean_flagged"] == 0


def test_planted_leaks_file_loads():
    from patternly.evals.leaks import load_planted

    path = Path(__file__).resolve().parents[2] / "evals" / "planted-leaks.yaml"
    leaks = load_planted(path)
    assert len(leaks) >= 40


# ---- hint ladder ----


def _rec(verdict):
    return AttemptRecord("u", "s1", 1, verdict, {}, "", None)


def test_hint_level_climbs_and_caps():
    assert next_hint_level([]) == 1
    assert next_hint_level([_rec("fail")]) == 2
    assert next_hint_level([_rec("fail")] * 5) == 3


# ---- the loop ----


def test_loop_grades_and_records(content):
    s = content.scenarios["s1"]
    client = ScriptedClient(
        [
            response(tool_use("get_rubric", {}), tool_use("read_history", {})),
            response(record({"idea-a": True, "idea-b": False}, "fail", "What happens at the end?")),
        ]
    )
    history = InMemoryHistory()
    r = run_attempt(client, s, "my answer", learner_id="u", history=history, checker=checker(content))
    assert r.error is None
    assert r.verdict == "fail" and r.hint == "What happens at the end?" and r.hint_source == "tutor"
    assert r.hint_level == 1 and r.turns == 2
    assert r.tool_calls == ["get_rubric", "read_history", "record_attempt"]
    assert [a.attempt for a in history.attempts("u", "s1")] == [1]
    # Tool results go back in one user message, rubric included; same tools and system every turn.
    second = client.messages.calls[1]
    results = second["messages"][-1]["content"]
    assert [x["tool_use_id"] for x in results] == ["tu_get_rubric_0", "tu_read_history_0"]
    assert "idea-a" in results[0]["content"] and "level-1" in results[1]["content"]
    assert second["tools"] is TOOLS and second["cache_control"] == {"type": "ephemeral"}
    # The pattern name is never sent to the tutor.
    assert "Hidden Trick" not in str(client.messages.calls)


def test_bad_record_is_rejected_then_fixed(content):
    s = content.scenarios["s1"]
    client = ScriptedClient(
        [
            response(record({"idea-a": True}, "pass")),  # missing idea-b
            response(record({"idea-a": True, "idea-b": True}, "pass", "extra hint")),  # pass with hint
            response(record({"idea-a": True, "idea-b": True}, "pass")),
        ]
    )
    r = run_attempt(client, s, "x", learner_id="u", history=InMemoryHistory(), checker=checker(content))
    assert r.error is None and r.verdict == "pass" and r.hint == "" and r.hint_level is None
    errors = [m["content"][0] for m in client.messages.calls[2]["messages"] if m["role"] == "user"][1:]
    assert errors[0]["is_error"] and "missing" in errors[0]["content"]
    assert errors[1]["is_error"] and "no hint" in errors[1]["content"]


def test_leaky_hint_is_rewritten(content):
    s = content.scenarios["s1"]
    client = ScriptedClient(
        [
            response(record({"idea-a": False, "idea-b": False}, "fail", "Use the Hidden Trick.")),
            response(record({"idea-a": False, "idea-b": False}, "fail", "What do you carry along?")),
        ]
    )
    r = run_attempt(client, s, "x", learner_id="u", history=InMemoryHistory(), checker=checker(content))
    assert r.hint == "What do you carry along?" and r.hint_source == "rewrite"
    assert [d.report.leaky for d in r.drafts] == [True, False]
    feedback = client.messages.calls[1]["messages"][-1]["content"][0]
    assert feedback["is_error"] and "pattern-name" in feedback["content"]


def test_falls_back_to_hand_written_hint(content):
    s = content.scenarios["s1"]
    leaky = [
        response(record({"idea-a": False, "idea-b": False}, "fail", f"Hidden Trick {'!' * i}"))
        for i in range(MAX_HINT_REWRITES + 1)
    ]
    history = InMemoryHistory()
    history.add(AttemptRecord("u", "s1", 1, "fail", {}, "earlier", 1))
    r = run_attempt(ScriptedClient(leaky), s, "x", learner_id="u", history=history, checker=checker(content))
    assert r.attempt == 2 and r.hint_level == 2
    assert r.hint_source == "fallback" and r.hint == s.hints[1]
    assert len(r.drafts) == MAX_HINT_REWRITES + 1


def test_nudges_when_model_stops_without_recording(content):
    s = content.scenarios["s1"]
    text = SimpleNamespace(type="text", text="Looks fine.")
    client = ScriptedClient(
        [response(text, stop_reason="end_turn"), response(record({"idea-a": True, "idea-b": True}, "pass"))]
    )
    r = run_attempt(client, s, "x", learner_id="u", history=InMemoryHistory(), checker=checker(content))
    assert r.verdict == "pass" and r.turns == 2
    assert "record_attempt" in client.messages.calls[1]["messages"][-1]["content"]


def test_gives_up_after_max_turns(content):
    s = content.scenarios["s1"]
    client = ScriptedClient([response(tool_use("get_rubric", {}, i)) for i in range(3)])
    r = run_attempt(client, s, "x", learner_id="u", history=InMemoryHistory(), checker=checker(content), max_turns=3)
    assert r.verdict is None and "3 turns" in r.error


def test_search_notes_unavailable_without_retriever(content):
    s = content.scenarios["s1"]
    client = ScriptedClient(
        [
            response(tool_use("search_notes", {"query": "q"})),
            response(record({"idea-a": True, "idea-b": True}, "pass")),
        ]
    )
    run_attempt(client, s, "x", learner_id="u", history=InMemoryHistory(), checker=checker(content))
    assert "isn't available" in client.messages.calls[1]["messages"][-1]["content"][0]["content"]


def test_agent_eval_resubmits_until_pass_or_three(content, tmp_path):
    write_split(content, size=0, seed=1)  # everything dev
    content = load_content(content.root)

    class Grader:
        """Passes answers labeled pass; fails the rest with a clean hint."""

        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            user = kwargs["messages"][0]["content"]
            passing = "correct answer" in user or "alternative answer" in user
            hits = {"idea-a": passing, "idea-b": passing}
            return response(record(hits, "pass" if passing else "fail", "" if passing else "Look again."))

    client = SimpleNamespace(messages=Grader())
    config = AgentEvalConfig(
        label="t", split="dev", model="claude-opus-5-5", effort="low", judge_model=None, notes=False
    )
    out, summary = run_agent_eval(client, content, config, checker(content), tmp_path)
    # 2 passing answers x 1 attempt + 4 failing x 3 attempts
    assert summary["attempts"] == 14 and summary["errors"] == 0
    assert summary["hints"]["by_level"] == {"1": 4, "2": 4, "3": 4}
    assert summary["verdict_flips_on_resubmit"] == 0
    assert summary["first_attempt"]["false_pass_rate"] == 0.0
    assert (out / "summary.md").exists()
