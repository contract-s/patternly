"""Latency and cost from a trace file."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from patternly.evals.traces import format_report, load, percentile, report

T0 = int(datetime(2026, 11, 13, tzinfo=UTC).timestamp() * 1e9)


def span(name, ms, *, start=T0, status="UNSET", **attrs):
    return {"name": name, "start_ns": start, "duration_ms": ms, "status": status, "attributes": attrs}


def write(path, spans):
    path.write_text("".join(json.dumps(s) + "\n" for s in spans))
    return path


def test_percentile_is_nearest_rank():
    values = list(range(1, 21))  # 1..20
    assert percentile(values, 50) == 10
    assert percentile(values, 95) == 19
    assert percentile([7.0], 95) == 7.0


def test_report_skips_errors_for_latency_and_cost():
    spans = [
        span("tutor.attempt", 8000, **{"patternly.cost_usd": 0.02, "patternly.turns": 2}),
        span("tutor.attempt", 12000, **{"patternly.cost_usd": 0.03, "patternly.turns": 3}),
        span("tutor.attempt", 500, status="ERROR", **{"patternly.cost_usd": 0.001}),
        span("POST /lessons/today/attempts", 8100),
        span("GET /lessons/today", 5),
    ]
    r = report(spans)
    assert (r["attempts"], r["errors"]) == (3, 1)
    assert r["attempt_latency_s"]["p95"] == 12.0 and r["attempt_latency_s"]["n"] == 2
    assert r["request_latency_s"]["n"] == 1
    assert r["cost_usd"]["mean"] == 0.025 and r["total_cost_usd"] == 0.05
    text = format_report(r)
    assert "Graded attempts: 3 (1 errors)" in text and "p95 12.00" in text


def test_empty_report_says_no_data():
    text = format_report(report([span("GET /me", 3)]))
    assert "Graded attempts: 0" in text and "no data" in text


def test_load_filters_by_start(tmp_path):
    later = T0 + 86_400 * 10**9
    path = write(tmp_path / "s.jsonl", [span("a", 1), span("b", 1, start=later)])
    assert [s["name"] for s in load(path, since=datetime(2026, 11, 14, tzinfo=UTC))] == ["b"]
    assert len(load(path)) == 2


def test_trace_report_command(tmp_path, capsys, monkeypatch):
    from patternly.cli import main

    monkeypatch.delenv("PATTERNLY_TRACE_FILE", raising=False)
    assert main(["trace-report"]) == 1
    path = write(tmp_path / "s.jsonl", [span("tutor.attempt", 9000, **{"patternly.cost_usd": 0.02})])
    assert main(["trace-report", "--file", str(path), "--since", "2026-11-13"]) == 0
    out = capsys.readouterr().out
    assert "Graded attempts: 1 (0 errors)" in out and "p95 9.00" in out
