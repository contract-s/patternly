"""Offline tests for the baseline grader and eval metrics. No API calls."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from patternly.content.loader import load_content
from patternly.content.split import write_split
from patternly.evals.metrics import per_run_metrics, summarize
from patternly.evals.runner import EvalConfig, run_eval
from patternly.tutor.baseline import Grade, GradeError, ItemCall, build_user_message, check_grade, grade_answer

from .conftest import answer_set, scenario


class FakeMessages:
    """Answers every call with a grade built by `decide(user_message)`."""

    def __init__(self, decide, stop_reason="end_turn"):
        self.decide = decide
        self.stop_reason = stop_reason
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        g = self.decide(kwargs["messages"][0]["content"])
        parsed = None
        if g is not None:
            parsed = kwargs["output_format"](
                items={
                    "item_" + c.rubric_id.replace("-", "_"): {"evidence": c.evidence, "hit": c.hit} for c in g.items
                },
                verdict=g.verdict,
                hint=g.hint,
            )
        return SimpleNamespace(
            parsed_output=parsed,
            stop_reason=self.stop_reason,
            usage=SimpleNamespace(input_tokens=1000, output_tokens=500),
        )


class FakeClient:
    def __init__(self, decide, **kw):
        self.messages = FakeMessages(decide, **kw)


def grade(hits: dict[str, bool], verdict="pass", hint="") -> Grade:
    return Grade(
        items=[ItemCall(rubric_id=k, evidence="e", hit=v) for k, v in hits.items()], verdict=verdict, hint=hint
    )


@pytest.fixture
def one_scenario(content_dir):
    content_dir.patterns([{"id": "p", "name": "Hidden Trick"}])
    content_dir.scenario(scenario("s", "p"))
    content_dir.answers(answer_set("s"))
    return load_content(content_dir.root)


def test_prompt_leaves_out_pattern_and_reference(one_scenario):
    s = one_scenario.scenarios["s"]
    msg = build_user_message(s, "my answer")
    assert "idea-a: First idea." in msg and "my answer" in msg
    assert "Hidden Trick" not in msg and s.reference_solution.strip() not in msg


def test_check_grade_reorders_and_rejects_bad_ids(one_scenario):
    s = one_scenario.scenarios["s"]
    ok = check_grade(grade({"idea-b": True, "idea-a": False}), s)
    assert [c.rubric_id for c in ok.items] == ["idea-a", "idea-b"]
    with pytest.raises(GradeError, match="missing"):
        check_grade(grade({"idea-a": True}), s)
    with pytest.raises(GradeError, match="unexpected"):
        check_grade(grade({"idea-a": True, "idea-b": True, "idea-z": True}), s)


def test_grade_answer_sends_settings_and_prices_usage(one_scenario):
    client = FakeClient(lambda _msg: grade({"idea-a": True, "idea-b": True}))
    g, usage = grade_answer(client, one_scenario.scenarios["s"], "text", model="claude-opus-5-5", effort="low")
    call = client.messages.calls[0]
    assert call["output_config"] == {"effort": "low"}
    schema = call["output_format"].model_json_schema()
    items = schema["$defs"]["RubricCalls"]
    assert sorted(items["required"]) == ["item_idea_a", "item_idea_b"]
    assert "temperature" not in call
    assert g.verdict == "pass"
    assert usage.cost_usd == pytest.approx((1000 * 4 + 500 * 20) / 1e6)


def test_grade_answer_refusal_keeps_usage(one_scenario):
    client = FakeClient(lambda _msg: None, stop_reason="refusal")
    with pytest.raises(GradeError) as exc:
        grade_answer(client, one_scenario.scenarios["s"], "text")
    assert exc.value.usage is not None and exc.value.usage.output_tokens == 500


def rec(key, run, kind, label_verdict, labels, tutor_items, tutor_verdict, hint_leak=False):
    return {
        "key": key,
        "run": run,
        "scenario": "s",
        "kind": kind,
        "label_verdict": label_verdict,
        "labels": labels,
        "tutor_items": tutor_items,
        "tutor_verdict": tutor_verdict,
        "hint_names_pattern": hint_leak,
        "error": None,
        "cost_usd": 0.01,
        "latency_s": 2.0,
        "input_tokens": 1000,
        "output_tokens": 500,
    }


def test_per_run_metrics_counts():
    records = [
        # labeled fail, tutor passes: a false pass. One of two items disagrees.
        rec("s/a", 1, "vague", "fail", {"x": "miss", "y": "hit"}, {"x": True, "y": True}, "pass"),
        # labeled fail, tutor fails, gives a leaky hint.
        rec("s/b", 1, "partial", "fail", {"x": "hit", "y": "miss"}, {"x": True, "y": False}, "fail", hint_leak=True),
        # labeled pass alternative, tutor fails it: a false fail.
        rec("s/c", 1, "alternative", "pass", {"x": "miss", "y": "hit"}, {"x": False, "y": False}, "fail"),
    ]
    m = per_run_metrics(records)
    assert m["rubric_items"] == 6
    assert m["rubric_item_accuracy"] == pytest.approx(4 / 6)
    assert (m["tutor_hit_label_miss"], m["tutor_miss_label_hit"]) == (1, 1)
    assert m["false_pass_rate"] == pytest.approx(1 / 2)
    assert m["false_fail_rate"] == 1.0
    assert m["alternative_accept_rate"] == 0.0
    assert m["hint_names_pattern_rate"] == pytest.approx(1 / 2)


def test_summary_spread_flips_and_errors():
    base = {"x": "hit"}
    records = [
        rec("s/a", 1, "correct", "pass", base, {"x": True}, "pass"),
        rec("s/a", 2, "correct", "pass", base, {"x": False}, "fail"),
        rec("s/b", 1, "vague", "fail", {"x": "miss"}, {"x": False}, "fail"),
        rec("s/b", 2, "vague", "fail", {"x": "miss"}, {"x": False}, "fail") | {"error": "boom", "tutor_items": None},
    ]
    s = summarize(records)
    assert s["runs"] == 2 and s["errors"] == 1
    assert s["metrics"]["rubric_item_accuracy"] == {
        "mean": 0.5,
        "min": 0.0,
        "max": 1.0,
        "stdev": pytest.approx(0.7071, 1e-3),
    }
    assert s["verdict_flips"] == {"answers": 1, "keys": ["s/a"]}
    assert s["cost"]["total_usd"] == pytest.approx(0.04)


def test_run_eval_end_to_end_with_fake_client(content_dir, tmp_path):
    content_dir.full()
    content = load_content(content_dir.root)
    write_split(content, size=20, seed=1)
    content = load_content(content_dir.root)

    def decide(msg):
        # Pass everything and hit every item: right on correct answers, wrong elsewhere.
        return grade({"idea-a": True, "idea-b": True}, "pass")

    config = EvalConfig(label="t", split="dev", runs=2, model="claude-opus-5-5", effort="low", concurrency=4)
    out_dir, summary = run_eval(FakeClient(decide), content, config, tmp_path)
    assert summary["calls"] == 80 and summary["answers"] == 40 and summary["errors"] == 0
    sealed = {la.key for la in content.sealed_answers()}
    graded = {json.loads(line)["key"] for line in (out_dir / "calls.jsonl").read_text().splitlines()}
    assert graded.isdisjoint(sealed)
    assert summary["metrics"]["false_pass_rate"]["mean"] == 1.0
    assert (out_dir / "summary.md").read_text().startswith("# Eval: t")
