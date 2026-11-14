"""The tracing setup and the JSON Lines span exporter."""

from __future__ import annotations

import json

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from patternly import tracing


def test_exporter_writes_one_json_line_per_span(tmp_path):
    path = tmp_path / "traces" / "spans.jsonl"
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(tracing.JsonlExporter(path)))
    t = provider.get_tracer("test")
    with t.start_as_current_span("outer") as outer:
        outer.set_attribute("patternly.cost_usd", 0.02)
        with t.start_as_current_span("inner"):
            pass
    inner, outer = [json.loads(line) for line in path.read_text().splitlines()]
    assert (inner["name"], outer["name"]) == ("inner", "outer")
    assert inner["parent_id"] == outer["span_id"] and outer["parent_id"] is None
    assert inner["trace_id"] == outer["trace_id"]
    assert outer["attributes"] == {"patternly.cost_usd": 0.02}
    assert outer["duration_ms"] >= inner["duration_ms"] >= 0
    assert outer["status"] == "UNSET"


def test_setup_is_off_without_a_destination(monkeypatch):
    monkeypatch.delenv(tracing.TRACE_FILE_ENV, raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    assert tracing.setup("patternly-test") is None


def test_setup_with_a_trace_file(monkeypatch, tmp_path):
    installed = []
    monkeypatch.setattr(trace, "set_tracer_provider", installed.append)
    monkeypatch.setenv(tracing.TRACE_FILE_ENV, str(tmp_path / "spans.jsonl"))
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    provider = tracing.setup("patternly-test")
    assert installed == [provider]
    assert provider.resource.attributes["service.name"] == "patternly-test"
    with provider.get_tracer("t").start_as_current_span("hello"):
        pass
    provider.shutdown()  # flushes the batch processor
    assert json.loads((tmp_path / "spans.jsonl").read_text())["name"] == "hello"
