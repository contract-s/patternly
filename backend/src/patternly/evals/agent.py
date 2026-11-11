"""Run the Weekend 4 tutor loop over labeled answers, as a learner who resubmits the same answer.

Each answer is submitted up to three times (stopping once it passes), with a fresh history, so a
failing answer collects a level 1, 2, and 3 hint. Attempt 1 is comparable to the baseline grader.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..content.loader import Content, LabeledAnswer
from ..tutor.agent import AttemptResult, run_attempt
from ..tutor.history import InMemoryHistory
from ..tutor.leaks import LeakChecker
from .runner import select_answers

ATTEMPTS = 3


@dataclass(frozen=True)
class AgentEvalConfig:
    label: str
    split: str
    model: str
    effort: str
    judge_model: str | None  # None: no revealed-steps check
    notes: bool  # whether search_notes is backed by retrieval
    attempts: int = ATTEMPTS
    concurrency: int = 8
    limit: int | None = None


def _record(la: LabeledAnswer, r: AttemptResult, fallback_report=None) -> dict:
    return {
        "key": la.key,
        "scenario": la.scenario.id,
        "kind": la.answer.kind.value,
        "attempt": r.attempt,
        "label_verdict": la.answer.verdict.value,
        "labels": {k: v.value for k, v in la.answer.labels.items()},
        "tutor_items": {c.rubric_id: c.hit for c in r.items} if r.items else None,
        "tutor_evidence": {c.rubric_id: c.evidence for c in r.items} if r.items else None,
        "tutor_verdict": r.verdict,
        "hint_level": r.hint_level,
        "hint": r.hint,
        "hint_source": r.hint_source,
        "drafts": [
            {"hint": d.hint, "leaks": [[x.kind, x.detail] for x in d.report.leaks], "revealed": d.report.revealed}
            for d in r.drafts
        ],
        "fallback_leaks": [[x.kind, x.detail] for x in fallback_report.leaks] if fallback_report else None,
        "tool_calls": r.tool_calls,
        "turns": r.turns,
        "input_tokens": sum(u.total_input_tokens for u in r.usages),
        "cache_read_input_tokens": sum(u.cache_read_input_tokens for u in r.usages),
        "output_tokens": sum(u.output_tokens for u in r.usages),
        "tutor_cost_usd": sum(u.cost_usd for u in r.usages),
        "judge_cost_usd": sum(u.cost_usd for u in r.judge_usages),
        "cost_usd": r.cost_usd,
        "latency_s": r.latency_s,
        "error": r.error,
    }


def run_agent_eval(
    client,
    content: Content,
    config: AgentEvalConfig,
    checker: LeakChecker,
    out_root: Path,
    search: Callable[[str], list[str]] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> tuple[Path, dict]:
    answers = select_answers(content, config.split, config.limit)
    started_at = datetime.now().isoformat(timespec="seconds")
    out_dir = out_root / f"{started_at.replace(':', '')}_{config.label}"
    out_dir.mkdir(parents=True, exist_ok=False)
    meta = {**config.__dict__, "started_at": started_at, "answers": [la.key for la in answers]}
    (out_dir / "config.json").write_text(json.dumps(meta, indent=2))

    def work(la: LabeledAnswer) -> list[dict]:
        history = InMemoryHistory()
        out = []
        for _ in range(config.attempts):
            r = run_attempt(
                client,
                la.scenario,
                la.answer.text,
                learner_id="eval",
                history=history,
                checker=checker,
                search=search,
                model=config.model,
                effort=config.effort,
            )
            fallback_report = None
            if r.hint_source == "fallback":
                fallback_report = checker.check(
                    r.hint,
                    scenario=la.scenario,
                    level=r.hint_level,
                    learner_text=la.answer.text,
                    missed=[c.rubric_id for c in r.items if not c.hit],
                )
                if fallback_report.usage is not None:
                    r.judge_usages.append(fallback_report.usage)
            out.append(_record(la, r, fallback_report))
            if r.error or r.verdict == "pass":
                break
        return out

    records: list[dict] = []
    with ThreadPoolExecutor(max_workers=config.concurrency) as pool:
        futures = [pool.submit(work, la) for la in answers]
        for done, future in enumerate(as_completed(futures), start=1):
            records.extend(future.result())
            if progress:
                progress(done, len(answers))
    records.sort(key=lambda r: (r["key"], r["attempt"]))
    with (out_dir / "calls.jsonl").open("w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    summary = summarize(records)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (out_dir / "summary.md").write_text(render_markdown(summary, meta))
    return out_dir, summary


def _rate(n: int, d: int) -> float | None:
    return n / d if d else None


def _pctl(values: list[float], q: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[int(q) - 1]


def summarize(records: list[dict]) -> dict:
    ok = [r for r in records if r["error"] is None]
    first = [r for r in ok if r["attempt"] == 1]
    items_total = items_match = 0
    for r in first:
        for rid, label in r["labels"].items():
            items_total += 1
            items_match += r["tutor_items"][rid] == (label == "hit")
    label_fail = [r for r in first if r["label_verdict"] == "fail"]
    label_pass = [r for r in first if r["label_verdict"] == "pass"]
    alternatives = [r for r in first if r["kind"] == "alternative"]

    # The same answer resubmitted should get the same verdict.
    by_key: dict[str, list[dict]] = {}
    for r in ok:
        by_key.setdefault(r["key"], []).append(r)
    flips = sum(1 for rs in by_key.values() if len({r["tutor_verdict"] for r in rs}) > 1)

    hinted = [r for r in ok if r["tutor_verdict"] == "fail"]
    first_drafts = [r["drafts"][0] for r in hinted if r["drafts"]]
    draft_kinds = Counter(kind for d in first_drafts for kind in {x[0] for x in d["leaks"]})
    delivered_leaky = sum(1 for r in hinted if r["hint_source"] == "fallback" and r["fallback_leaks"])
    sources = Counter(r["hint_source"] for r in hinted)
    levels = Counter(r["hint_level"] for r in hinted)
    tools = Counter(t for r in ok for t in r["tool_calls"])
    costs = [r["cost_usd"] for r in ok]
    lat = [r["latency_s"] for r in ok]
    return {
        "attempts": len(records),
        "errors": len(records) - len(ok),
        "answers": len(by_key),
        "first_attempt": {
            "rubric_item_accuracy": _rate(items_match, items_total),
            "rubric_items": items_total,
            "false_pass_rate": _rate(sum(r["tutor_verdict"] == "pass" for r in label_fail), len(label_fail)),
            "false_fail_rate": _rate(sum(r["tutor_verdict"] == "fail" for r in label_pass), len(label_pass)),
            "alternative_acceptance": _rate(sum(r["tutor_verdict"] == "pass" for r in alternatives), len(alternatives)),
            "label_fail": len(label_fail),
            "label_pass": len(label_pass),
            "alternatives": len(alternatives),
        },
        "verdict_flips_on_resubmit": flips,
        "hints": {
            "total": len(hinted),
            "by_level": {str(k): v for k, v in sorted(levels.items())},
            "first_draft_leaky": sum(1 for d in first_drafts if d["leaks"]),
            "first_draft_leaks_by_kind": dict(draft_kinds),
            "by_source": dict(sources),
            "delivered_leaky": delivered_leaky,
        },
        "tool_calls": dict(tools),
        "tool_calls_per_attempt": _rate(sum(tools.values()), len(ok)),
        "turns_per_attempt": _rate(sum(r["turns"] for r in ok), len(ok)),
        "cost": {
            "total_usd": sum(costs),
            "per_attempt_usd": _rate(sum(costs), len(costs)),
            "judge_usd": sum(r["judge_cost_usd"] for r in ok),
            "cache_read_share_of_input": _rate(
                sum(r["cache_read_input_tokens"] for r in ok), sum(r["input_tokens"] for r in ok)
            ),
        },
        "latency_s": {"p50": _pctl(lat, 50), "p95": _pctl(lat, 95)},
    }


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def render_markdown(summary: dict, meta: dict) -> str:
    fa, h, c, lat = summary["first_attempt"], summary["hints"], summary["cost"], summary["latency_s"]
    judge = meta.get("judge_model") or "none (revealed-steps not checked)"
    lines = [
        f"# Tutor loop eval: {meta['label']}",
        "",
        f"Model `{meta['model']}`, effort `{meta['effort']}`, leak judge `{judge}`, note search "
        f"{'on' if meta.get('notes') else 'off'}. {summary['answers']} {meta['split']} answers, up to "
        f"{meta['attempts']} attempts each (resubmitting the same answer). {summary['attempts']} attempts, "
        f"{summary['errors']} errors.",
        "",
        "## Grading (first attempt)",
        "",
        "| Metric | Result | Sample |",
        "|---|---|---|",
        f"| Rubric-item accuracy | {_pct(fa['rubric_item_accuracy'])} | {fa['rubric_items']} items |",
        f"| False-pass rate | {_pct(fa['false_pass_rate'])} | {fa['label_fail']} labeled fail |",
        f"| False-fail rate | {_pct(fa['false_fail_rate'])} | {fa['label_pass']} labeled pass |",
        f"| Alternative acceptance | {_pct(fa['alternative_acceptance'])} | {fa['alternatives']} alternatives |",
        f"| Verdict changes on resubmission | {summary['verdict_flips_on_resubmit']} | {summary['answers']} answers |",
        "",
        "## Hints",
        "",
        f"- Hints given: {h['total']} (by level: "
        + ", ".join(f"level {k}: {v}" for k, v in h["by_level"].items())
        + ")",
        f"- First drafts the checker rejected: {h['first_draft_leaky']} of {h['total']} "
        + (
            f"({', '.join(f'{k} {v}' for k, v in sorted(h['first_draft_leaks_by_kind'].items()))})"
            if h["first_draft_leaks_by_kind"]
            else ""
        ),
        "- Delivered hints by source: " + ", ".join(f"{k} {v}" for k, v in sorted(h["by_source"].items())),
        f"- Delivered hints the checker flags: {h['delivered_leaky']} of {h['total']}",
        "",
        "## Loop",
        "",
        "- Tool calls: " + ", ".join(f"{k} {v}" for k, v in sorted(summary["tool_calls"].items())),
        f"- Per attempt: {summary['tool_calls_per_attempt'] or 0:.1f} tool calls, "
        f"{summary['turns_per_attempt'] or 0:.1f} model turns",
        f"- Cost: ${c['total_usd']:.2f} total, ${c['per_attempt_usd'] or 0:.4f} per attempt "
        f"(judge ${c['judge_usd']:.4f}); input from cache {_pct(c['cache_read_share_of_input'])}",
        f"- Latency per attempt: p50 {lat['p50'] or 0:.1f} s, p95 {lat['p95'] or 0:.1f} s",
        "",
    ]
    return "\n".join(lines)
