"""Latency and cost per attempt, from the trace file the API writes (see patternly.tracing).

A graded attempt is one `tutor.attempt` span; its request is the `POST /lessons/today/attempts` server span
around it, which adds the database work. Percentiles are nearest-rank, so every value reported is one that
was measured.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

ATTEMPT_SPAN = "tutor.attempt"
REQUEST_SPAN = "POST /lessons/today/attempts"


def load(path: str | Path, since: datetime | None = None) -> list[dict]:
    """Spans from a JSON Lines trace file, optionally only those that started at or after `since`."""
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        span = json.loads(line)
        if since is None or span["start_ns"] >= since.timestamp() * 1e9:
            out.append(span)
    return out


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile: the smallest value with at least p% of values at or below it."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def _summary(values: list[float]) -> dict | None:
    if not values:
        return None
    return {
        "n": len(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "max": max(values),
        "mean": sum(values) / len(values),
    }


def report(spans: list[dict]) -> dict:
    attempts = [s for s in spans if s["name"] == ATTEMPT_SPAN]
    ok = [s for s in attempts if s["status"] != "ERROR"]
    requests = [s for s in spans if s["name"] == REQUEST_SPAN]
    costs = [s["attributes"].get("patternly.cost_usd", 0.0) for s in ok]
    starts = [s["start_ns"] for s in attempts]
    return {
        "attempts": len(attempts),
        "errors": len(attempts) - len(ok),
        "first": _iso(min(starts)) if starts else None,
        "last": _iso(max(starts)) if starts else None,
        "attempt_latency_s": _summary([s["duration_ms"] / 1000 for s in ok]),
        "request_latency_s": _summary([s["duration_ms"] / 1000 for s in requests]),
        "cost_usd": _summary(costs),
        "total_cost_usd": sum(costs),
        "turns": _summary([s["attributes"].get("patternly.turns", 0) for s in ok]),
    }


def _iso(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, UTC).isoformat(timespec="seconds")


def format_report(r: dict) -> str:
    lines = [f"Graded attempts: {r['attempts']} ({r['errors']} errors)"]
    if r["first"]:
        lines.append(f"From {r['first']} to {r['last']}")
    rows = [
        ("Tutor latency (s)", r["attempt_latency_s"], "{:.2f}"),
        ("Request latency (s)", r["request_latency_s"], "{:.2f}"),
        ("Cost per attempt ($)", r["cost_usd"], "{:.4f}"),
        ("Model turns", r["turns"], "{:.1f}"),
    ]
    for label, s, fmt in rows:
        if s is None:
            lines.append(f"{label:<22} no data")
            continue
        vals = "  ".join(f"{k} {fmt.format(s[k])}" for k in ("p50", "p95", "max", "mean"))
        lines.append(f"{label:<22} n={s['n']:<4} {vals}")
    lines.append(f"Total cost: ${r['total_cost_usd']:.4f}")
    return "\n".join(lines)
