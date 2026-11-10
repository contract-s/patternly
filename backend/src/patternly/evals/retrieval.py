"""Retrieval hit rate: does the scenario's pattern appear among the top notes for a learner's answer?

Runs on development answers only. Two query forms are measured, because the tutor can search
with the learner's answer alone or with the scenario prompt in front of it.
"""

from __future__ import annotations

import json
import statistics
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from ..content.loader import Content
from ..retrieval.search import METHODS, Retriever, top_patterns

QUERY_FORMS = ["answer", "scenario+answer"]


def make_query(form: str, prompt: str, answer: str) -> str:
    if form == "answer":
        return answer
    if form == "scenario+answer":
        return f"{prompt.strip()}\n\n{answer}"
    raise ValueError(form)


def run_retrieval_eval(retriever: Retriever, content: Content, methods: list[str] = METHODS) -> dict:
    answers = content.dev_answers()
    records = []
    for la in answers:
        for form in QUERY_FORMS:
            query = make_query(form, la.scenario.prompt, la.answer.text)
            for method in methods:
                start = time.perf_counter()
                chunks = retriever.search(query, method, limit=30)
                latency = time.perf_counter() - start
                ranked = top_patterns(chunks, k=len(content.patterns))
                target = la.scenario.pattern
                rank = ranked.index(target) + 1 if target in ranked else None
                records.append(
                    {
                        "key": la.key,
                        "kind": la.answer.kind.value,
                        "form": form,
                        "method": method,
                        "target": target,
                        "top3": ranked[:3],
                        "rank": rank,
                        "latency_s": latency,
                    }
                )
    return {"answers": len(answers), "records": records, "summary": summarize(records)}


def summarize(records: list[dict]) -> dict:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in records:
        groups[(r["form"], r["method"])].append(r)
    out = {}
    for (form, method), rs in groups.items():
        by_kind: dict[str, list[bool]] = defaultdict(list)
        for r in rs:
            by_kind[r["kind"]].append(r["rank"] is not None and r["rank"] <= 3)
        latencies = sorted(r["latency_s"] for r in rs)
        out[f"{form} | {method}"] = {
            "form": form,
            "method": method,
            "n": len(rs),
            "hit_at_1": statistics.fmean(r["rank"] == 1 for r in rs),
            "hit_at_3": statistics.fmean(r["rank"] is not None and r["rank"] <= 3 for r in rs),
            "mrr": statistics.fmean(1 / r["rank"] if r["rank"] else 0.0 for r in rs),
            "hit_at_3_by_kind": {k: statistics.fmean(v) for k, v in sorted(by_kind.items())},
            "latency_p50_s": latencies[len(latencies) // 2],
        }
    return out


def render_markdown(result: dict, config: dict) -> str:
    lines = [
        f"# Retrieval eval: {config['label']}",
        "",
        f"- {result['answers']} development answers; target is the scenario's pattern",
        f"- Embeddings `{config['embed_model']}`, reranker `{config['rerank_model']}`",
        f"- Date: {config['started_at']}",
        "",
        "| Query | Method | Hit@1 | Hit@3 | MRR | p50 latency |",
        "|---|---|---|---|---|---|",
    ]
    for s in result["summary"].values():
        lines.append(
            f"| {s['form']} | {s['method']} | {s['hit_at_1']:.1%} | {s['hit_at_3']:.1%} | "
            f"{s['mrr']:.3f} | {s['latency_p50_s'] * 1000:.0f} ms |"
        )
    kinds = sorted(next(iter(result["summary"].values()))["hit_at_3_by_kind"])
    lines += ["", "Hit@3 by answer type:", "", "| Query | Method | " + " | ".join(kinds) + " |"]
    lines.append("|---|---|" + "---|" * len(kinds))
    for s in result["summary"].values():
        cells = " | ".join(f"{s['hit_at_3_by_kind'][k]:.0%}" for k in kinds)
        lines.append(f"| {s['form']} | {s['method']} | {cells} |")
    return "\n".join(lines) + "\n"


def save(result: dict, config: dict, out_root: Path) -> Path:
    out_dir = out_root / f"{config['started_at'].replace(':', '')}_{config['label']}"
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "config.json").write_text(json.dumps(config, indent=2))
    with (out_dir / "records.jsonl").open("w") as f:
        for r in result["records"]:
            f.write(json.dumps(r) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(result["summary"], indent=2))
    (out_dir / "summary.md").write_text(render_markdown(result, config))
    return out_dir


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")
