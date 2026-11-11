"""Does the leak checker catch planted leaks, and leave the hand-written hints alone?

Planted leaks live in evals/planted-leaks.yaml: hints written on purpose to give too much away, each
tagged with the leak kind it should be caught for. The clean set is every scenario's three
hand-written hints, checked at their own level against a learner who has stated nothing yet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from ..content.loader import Content
from ..tutor.leaks import LeakChecker

KINDS = ["pattern-name", "copied-solution", "revealed-steps"]
NONE = "none"  # a tricky hint that should not be flagged
DETERMINISTIC = {"pattern-name", "copied-solution"}


class PlantedLeak(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario: str
    level: int = Field(ge=1, le=3)
    kind: str
    hint: str
    learner_text: str = ""
    missed: list[str] | None = None  # rubric ids the learner hasn't stated; default all


def load_planted(path: Path) -> list[PlantedLeak]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    leaks = [PlantedLeak.model_validate(x) for x in data["leaks"]]
    for leak in leaks:
        if leak.kind not in (*KINDS, NONE):
            raise ValueError(f"unknown leak kind '{leak.kind}' (expected one of {KINDS})")
    return leaks


@dataclass(frozen=True)
class Case:
    source: str  # "planted", "tricky" (planted but fine), or "clean" (hand-written)
    scenario: str
    level: int
    expected: str | None  # leak kind for planted, None for clean
    hint: str
    learner_text: str = ""
    missed: list[str] | None = None


def cases(content: Content, planted: list[PlantedLeak]) -> list[Case]:
    out = [
        Case(
            "tricky" if p.kind == NONE else "planted",
            p.scenario,
            p.level,
            None if p.kind == NONE else p.kind,
            p.hint,
            p.learner_text,
            p.missed,
        )
        for p in planted
    ]
    for sid, s in sorted(content.scenarios.items()):
        for level, hint in enumerate(s.hints, start=1):
            out.append(Case("clean", sid, level, None, hint))
    for c in out:
        if c.scenario not in content.scenarios:
            raise ValueError(f"planted leak for unknown scenario '{c.scenario}'")
    return out


def run_leak_eval(content: Content, planted: list[PlantedLeak], checker: LeakChecker) -> list[dict]:
    records = []
    for c in cases(content, planted):
        if c.expected in DETERMINISTIC or c.expected is None or checker.judge is not None:
            report = checker.check(
                c.hint,
                scenario=content.scenarios[c.scenario],
                level=c.level,
                learner_text=c.learner_text,
                missed=c.missed,
            )
            found = sorted({leak.kind for leak in report.leaks})
            records.append(
                {
                    **c.__dict__,
                    "found": found,
                    "caught": bool(found),
                    "detail": report.feedback(),
                    "revealed": report.revealed,
                    "judged": report.judged,
                    "cost_usd": report.usage.cost_usd if report.usage else 0.0,
                }
            )
    return records


def summarize(records: list[dict], judged: bool) -> dict:
    planted = [r for r in records if r["source"] == "planted"]
    clean = [r for r in records if r["source"] == "clean"]
    tricky = [r for r in records if r["source"] == "tricky"]
    by_kind = {}
    for kind in KINDS:
        rs = [r for r in planted if r["expected"] == kind]
        if rs:
            by_kind[kind] = {"caught": sum(r["caught"] for r in rs), "total": len(rs)}
    clean_flags: dict[str, int] = {}
    for r in clean:
        for kind in r["found"]:
            clean_flags[kind] = clean_flags.get(kind, 0) + 1
    return {
        "judge": judged,
        "planted_caught": sum(r["caught"] for r in planted),
        "planted_total": len(planted),
        "by_kind": by_kind,
        "clean_flagged": sum(r["caught"] for r in clean),
        "clean_total": len(clean),
        "clean_flags_by_kind": clean_flags,
        "tricky_flagged": sum(r["caught"] for r in tricky),
        "tricky_total": len(tricky),
        "cost_usd": sum(r["cost_usd"] for r in records),
    }


def _pct(n: int, d: int) -> str:
    return f"{n / d:.1%} ({n} of {d})" if d else "n/a"


def render_markdown(summary: dict, label: str, judge_model: str | None) -> str:
    lines = [
        f"# Leak checker: {label}",
        "",
        "Checks: pattern name, copied reference solution"
        + (
            f", revealed steps (judge: `{judge_model}`)"
            if summary["judge"]
            else " (no judge; revealed-steps leaks not checked)"
        ),
        "",
        "| Set | Flagged |",
        "|---|---|",
        f"| Planted leaks (all) | {_pct(summary['planted_caught'], summary['planted_total'])} |",
    ]
    for kind, v in summary["by_kind"].items():
        lines.append(f"| Planted: {kind} | {_pct(v['caught'], v['total'])} |")
    lines.append(
        "| Tricky planted hints that are fine (should pass) | "
        f"{_pct(summary['tricky_flagged'], summary['tricky_total'])} |"
    )
    lines.append(f"| Hand-written hints (should pass) | {_pct(summary['clean_flagged'], summary['clean_total'])} |")
    if summary["clean_flags_by_kind"]:
        lines += [
            "",
            "Hand-written hints flagged, by kind: "
            + ", ".join(f"{k} {v}" for k, v in sorted(summary["clean_flags_by_kind"].items())),
        ]
    lines += ["", f"Judge cost: ${summary['cost_usd']:.4f}", ""]
    return "\n".join(lines)


def save(records: list[dict], summary: dict, out_root: Path, label: str, judge_model: str | None) -> Path:
    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "")
    out = out_root / f"{stamp}_{label}"
    out.mkdir(parents=True, exist_ok=False)
    with (out / "cases.jsonl").open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    (out / "summary.md").write_text(render_markdown(summary, label, judge_model))
    return out
