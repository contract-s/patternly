"""Turn per-call grading records into the numbers the plan asks for.

Pure functions over plain dicts, so they're easy to test and to re-run on saved results.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict

from ..content.loader import Content
from ..content.validate import _mentions


def hint_names_pattern(content: Content, scenario_id: str, hint: str, answer_text: str = "") -> bool:
    """True if the hint names the pattern (or an alias) that the learner hadn't already written.

    Echoing the learner's own words ("is that what your heap puts on top?") gives nothing away.
    """
    scenario = content.scenarios[scenario_id]
    pattern = content.patterns.get(scenario.pattern)
    if pattern is None or not hint:
        return False
    return any(
        _mentions(hint, phrase) and not _mentions(answer_text, phrase) for phrase in (pattern.name, *pattern.aliases)
    )


def _rate(numer: int, denom: int) -> float | None:
    return numer / denom if denom else None


def per_run_metrics(records: list[dict]) -> dict:
    """Metrics for one run (one pass over every answer). Records with errors are skipped."""
    ok = [r for r in records if r["error"] is None]
    items_total = items_match = lenient = strict = 0
    for r in ok:
        for rid, label in r["labels"].items():
            tutor_hit = r["tutor_items"][rid]
            label_hit = label == "hit"
            items_total += 1
            items_match += tutor_hit == label_hit
            lenient += tutor_hit and not label_hit
            strict += label_hit and not tutor_hit
    labeled_fail = [r for r in ok if r["label_verdict"] == "fail"]
    labeled_pass = [r for r in ok if r["label_verdict"] == "pass"]
    alternatives = [r for r in ok if r["kind"] == "alternative"]
    hints = [r for r in ok if r["tutor_verdict"] == "fail"]
    return {
        "answers_graded": len(ok),
        "errors": len(records) - len(ok),
        "rubric_items": items_total,
        "rubric_item_accuracy": _rate(items_match, items_total),
        "tutor_hit_label_miss": lenient,
        "tutor_miss_label_hit": strict,
        "labeled_fail": len(labeled_fail),
        "false_pass_rate": _rate(sum(r["tutor_verdict"] == "pass" for r in labeled_fail), len(labeled_fail)),
        "labeled_pass": len(labeled_pass),
        "false_fail_rate": _rate(sum(r["tutor_verdict"] == "fail" for r in labeled_pass), len(labeled_pass)),
        "alternatives": len(alternatives),
        "alternative_accept_rate": _rate(sum(r["tutor_verdict"] == "pass" for r in alternatives), len(alternatives)),
        "hints_given": len(hints),
        "hint_names_pattern_rate": _rate(sum(r["hint_names_pattern"] for r in hints), len(hints)),
    }


def _spread(values: list[float | None]) -> dict | None:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return {
        "mean": statistics.fmean(vals),
        "min": min(vals),
        "max": max(vals),
        "stdev": statistics.stdev(vals) if len(vals) > 1 else 0.0,
    }


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return ordered[idx]


RATE_KEYS = [
    "rubric_item_accuracy",
    "false_pass_rate",
    "false_fail_rate",
    "alternative_accept_rate",
    "hint_names_pattern_rate",
]


def summarize(records: list[dict]) -> dict:
    by_run: dict[int, list[dict]] = defaultdict(list)
    for r in records:
        by_run[r["run"]].append(r)
    runs = {run: per_run_metrics(recs) for run, recs in sorted(by_run.items())}

    ok = [r for r in records if r["error"] is None]

    # How often the same answer gets a different verdict on different runs.
    verdicts: dict[str, set[str]] = defaultdict(set)
    for r in ok:
        verdicts[r["key"]].add(r["tutor_verdict"])
    flipped = sorted(k for k, v in verdicts.items() if len(v) > 1)

    pass_by_kind = Counter()
    graded_by_kind = Counter()
    for r in ok:
        graded_by_kind[r["kind"]] += 1
        pass_by_kind[r["kind"]] += r["tutor_verdict"] == "pass"

    costs = [r["cost_usd"] for r in records if r["cost_usd"] is not None]
    latencies = [r["latency_s"] for r in records if r["latency_s"] is not None]
    out_tokens = [r["output_tokens"] for r in records if r["output_tokens"] is not None]
    in_tokens = [r["input_tokens"] for r in records if r["input_tokens"] is not None]

    return {
        "runs": len(runs),
        "calls": len(records),
        "errors": len(records) - len(ok),
        "answers": len({r["key"] for r in records}),
        "metrics": {key: _spread([m[key] for m in runs.values()]) for key in RATE_KEYS},
        "per_run": runs,
        "tutor_pass_rate_by_kind": {kind: pass_by_kind[kind] / graded_by_kind[kind] for kind in sorted(graded_by_kind)},
        "verdict_flips": {"answers": len(flipped), "keys": flipped},
        "cost": {
            "total_usd": sum(costs),
            "per_call_usd": statistics.fmean(costs) if costs else None,
            "mean_input_tokens": statistics.fmean(in_tokens) if in_tokens else None,
            "mean_output_tokens": statistics.fmean(out_tokens) if out_tokens else None,
        },
        "latency_s": {"p50": _percentile(latencies, 50), "p95": _percentile(latencies, 95)},
    }


def _pct(spread: dict | None) -> str:
    if spread is None:
        return "n/a"
    return f"{spread['mean']:.1%} (range {spread['min']:.1%}–{spread['max']:.1%})"


def render_markdown(summary: dict, config: dict) -> str:
    m = summary["metrics"]
    run0 = next(iter(summary["per_run"].values()), {})
    lines = [
        f"# Eval: {config['label']}",
        "",
        f"- Split: **{config['split']}**, {summary['answers']} answers × {summary['runs']} runs "
        f"= {summary['calls']} calls ({summary['errors']} errors)",
        f"- Model: `{config['model']}`, effort `{config['effort']}`, notes: {config.get('grounding', 'none')}",
        f"- Date: {config['started_at']}",
        "",
        "| Metric | Result | Per-run sample size |",
        "|---|---|---|",
        f"| Rubric-item accuracy | {_pct(m['rubric_item_accuracy'])} | {run0.get('rubric_items', 0)} rubric items |",
        f"| False-pass rate | {_pct(m['false_pass_rate'])} | {run0.get('labeled_fail', 0)} answers labeled fail |",
        f"| False-fail rate | {_pct(m['false_fail_rate'])} | {run0.get('labeled_pass', 0)} answers labeled pass |",
        f"| Alternative-solution acceptance | {_pct(m['alternative_accept_rate'])} | "
        f"{run0.get('alternatives', 0)} alternative answers |",
        f"| Hints naming the pattern | {_pct(m['hint_names_pattern_rate'])} | hints given per run (varies) |",
        "",
        f"- Answers whose verdict changed between runs: {summary['verdict_flips']['answers']} of {summary['answers']}",
        f"- Cost: ${summary['cost']['total_usd']:.2f} total, "
        f"${(summary['cost']['per_call_usd'] or 0):.4f} per call; "
        f"latency p50 {summary['latency_s']['p50'] or 0:.1f}s, p95 {summary['latency_s']['p95'] or 0:.1f}s",
        "",
        "Tutor pass rate by answer type:",
        "",
    ]
    for kind, rate in summary["tutor_pass_rate_by_kind"].items():
        lines.append(f"- {kind}: {rate:.0%}")
    return "\n".join(lines) + "\n"
