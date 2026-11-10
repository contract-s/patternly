"""Run the tutor over labeled answers several times and save every call plus a summary."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..content.loader import Content, LabeledAnswer
from ..tutor.baseline import GradeError, MessagesClient, grade_answer
from .metrics import hint_names_pattern, render_markdown, summarize


@dataclass(frozen=True)
class EvalConfig:
    label: str
    split: str  # "dev" or "sealed"
    runs: int
    model: str
    effort: str
    concurrency: int = 8
    limit: int | None = None  # first N answers only, for smoke tests
    grounding: str = "none"  # "none", or how notes were retrieved (e.g. "hybrid-top3")


def select_answers(content: Content, split: str, limit: int | None) -> list[LabeledAnswer]:
    if split == "dev":
        answers = content.dev_answers()
    elif split == "sealed":
        answers = content.sealed_answers()
    else:
        raise ValueError(f"unknown split '{split}'")
    return answers[:limit] if limit else answers


def _record(
    la: LabeledAnswer, run: int, content: Content, grade, usage, error: str | None, retrieved: list[str] | None
) -> dict:
    return {
        "key": la.key,
        "retrieved": retrieved,
        "run": run,
        "scenario": la.scenario.id,
        "kind": la.answer.kind.value,
        "label_verdict": la.answer.verdict.value,
        "labels": {k: v.value for k, v in la.answer.labels.items()},
        "tutor_items": {c.rubric_id: c.hit for c in grade.items} if grade else None,
        "tutor_evidence": {c.rubric_id: c.evidence for c in grade.items} if grade else None,
        "tutor_verdict": grade.verdict if grade else None,
        "hint": grade.hint if grade else None,
        "hint_names_pattern": hint_names_pattern(content, la.scenario.id, grade.hint, la.answer.text)
        if grade
        else None,
        "input_tokens": usage.input_tokens if usage else None,
        "output_tokens": usage.output_tokens if usage else None,
        "cost_usd": usage.cost_usd if usage else None,
        "latency_s": usage.latency_s if usage else None,
        "error": error,
    }


def run_eval(
    client: MessagesClient,
    content: Content,
    config: EvalConfig,
    out_root: Path,
    progress: Callable[[int, int], None] | None = None,
    retrieved: dict[str, list[str]] | None = None,
) -> tuple[Path, dict]:
    """`retrieved` maps answer key -> pattern ids whose notes go into the prompt (None: no notes)."""
    answers = select_answers(content, config.split, config.limit)
    jobs = [(la, run) for run in range(1, config.runs + 1) for la in answers]
    started_at = datetime.now().isoformat(timespec="seconds")
    out_dir = out_root / f"{started_at.replace(':', '')}_{config.label}"
    out_dir.mkdir(parents=True, exist_ok=False)
    meta = {**config.__dict__, "started_at": started_at, "answers": [la.key for la in answers]}
    if retrieved is not None:
        meta["retrieved"] = {la.key: retrieved[la.key] for la in answers}
    (out_dir / "config.json").write_text(json.dumps(meta, indent=2))

    records: list[dict] = []
    lock = threading.Lock()
    calls_file = (out_dir / "calls.jsonl").open("w")

    def work(la: LabeledAnswer, run: int) -> dict:
        pids = retrieved[la.key] if retrieved is not None else None
        notes = [content.notes[p].text for p in pids] if pids else None
        try:
            grade, usage = grade_answer(
                client, la.scenario, la.answer.text, model=config.model, effort=config.effort, notes=notes
            )
            return _record(la, run, content, grade, usage, None, pids)
        except GradeError as e:
            return _record(la, run, content, None, e.usage, str(e), pids)
        except Exception as e:  # API errors after the SDK's own retries: keep going, count it
            return _record(la, run, content, None, None, f"{type(e).__name__}: {e}", pids)

    try:
        with ThreadPoolExecutor(max_workers=config.concurrency) as pool:
            futures = [pool.submit(work, la, run) for la, run in jobs]
            for done, future in enumerate(as_completed(futures), start=1):
                rec = future.result()
                with lock:
                    records.append(rec)
                    calls_file.write(json.dumps(rec) + "\n")
                    calls_file.flush()
                if progress:
                    progress(done, len(jobs))
    finally:
        calls_file.close()

    records.sort(key=lambda r: (r["run"], r["key"]))
    summary = summarize(records)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (out_dir / "summary.md").write_text(render_markdown(summary, meta))
    return out_dir, summary
