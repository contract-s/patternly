"""Run the tutor over labeled answers several times and save every call plus a summary."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..content.loader import Content, LabeledAnswer
from ..tutor.baseline import GradeError, MessagesClient, batch_params, grade_answer, grade_batch_message
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
    batch: bool = False  # send through the Message Batches API (half price, no per-call latency)


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
        "input_tokens": usage.total_input_tokens if usage else None,  # cached + uncached
        "cache_creation_input_tokens": usage.cache_creation_input_tokens if usage else None,
        "cache_read_input_tokens": usage.cache_read_input_tokens if usage else None,
        "batch": usage.batch if usage else None,
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

    if config.batch:
        records = _run_batch(client, content, config, jobs, retrieved, progress, out_dir)
    else:
        records = _run_live(client, content, config, jobs, retrieved, progress)
    with (out_dir / "calls.jsonl").open("w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    records.sort(key=lambda r: (r["run"], r["key"]))
    summary = summarize(records)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (out_dir / "summary.md").write_text(render_markdown(summary, meta))
    return out_dir, summary


def _notes(content: Content, retrieved: dict[str, list[str]] | None, la: LabeledAnswer):
    pids = retrieved[la.key] if retrieved is not None else None
    return pids, ([content.notes[p].text for p in pids] if pids else None)


def _run_live(client, content, config, jobs, retrieved, progress) -> list[dict]:
    records: list[dict] = []
    lock = threading.Lock()

    def work(la: LabeledAnswer, run: int) -> dict:
        pids, notes = _notes(content, retrieved, la)
        try:
            grade, usage = grade_answer(
                client, la.scenario, la.answer.text, model=config.model, effort=config.effort, notes=notes
            )
            return _record(la, run, content, grade, usage, None, pids)
        except GradeError as e:
            return _record(la, run, content, None, e.usage, str(e), pids)
        except Exception as e:  # API errors after the SDK's own retries: keep going, count it
            return _record(la, run, content, None, None, f"{type(e).__name__}: {e}", pids)

    with ThreadPoolExecutor(max_workers=config.concurrency) as pool:
        futures = [pool.submit(work, la, run) for la, run in jobs]
        for done, future in enumerate(as_completed(futures), start=1):
            with lock:
                records.append(future.result())
            if progress:
                progress(done, len(jobs))
    return records


BATCH_POLL_SECONDS = 20


def _run_batch(client, content, config, jobs, retrieved, progress, out_dir: Path, poll=BATCH_POLL_SECONDS):
    """Submit every call as one Message Batch, wait for it, and grade the results."""
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    by_id: dict[str, tuple[LabeledAnswer, int]] = {}
    requests = []
    # Sorted by scenario so requests sharing a cached prefix sit together.
    for i, (la, run) in enumerate(sorted(jobs, key=lambda j: (j[0].scenario.id, j[1], j[0].key))):
        custom_id = f"call-{i:05d}"  # answer keys contain "/", which custom ids don't allow
        by_id[custom_id] = (la, run)
        _, notes = _notes(content, retrieved, la)
        params = batch_params(la.scenario, la.answer.text, model=config.model, effort=config.effort, notes=notes)
        requests.append(Request(custom_id=custom_id, params=MessageCreateParamsNonStreaming(**params)))

    batch = client.messages.batches.create(requests=requests)
    (out_dir / "batch.json").write_text(
        json.dumps({"batch_id": batch.id, "ids": {k: [v[0].key, v[1]] for k, v in by_id.items()}})
    )
    while batch.processing_status != "ended":
        time.sleep(poll)
        batch = client.messages.batches.retrieve(batch.id)
        if progress:
            counts = batch.request_counts
            progress(counts.succeeded + counts.errored + counts.canceled + counts.expired, len(jobs))

    records = []
    for result in client.messages.batches.results(batch.id):
        la, run = by_id[result.custom_id]
        pids, _ = _notes(content, retrieved, la)
        if result.result.type != "succeeded":
            detail = getattr(getattr(result.result, "error", None), "type", "")
            records.append(_record(la, run, content, None, None, f"batch {result.result.type} {detail}".strip(), pids))
            continue
        try:
            grade, usage = grade_batch_message(la.scenario, result.result.message, config.model)
            records.append(_record(la, run, content, grade, usage, None, pids))
        except GradeError as e:
            records.append(_record(la, run, content, None, e.usage, str(e), pids))
    return records
