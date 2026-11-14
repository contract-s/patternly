"""OpenTelemetry tracing.

Spans go to a JSON Lines file (PATTERNLY_TRACE_FILE) that `patternly trace-report` reads for latency and cost,
and to an OTLP collector too when OTEL_EXPORTER_OTLP_ENDPOINT is set. With neither, tracing is off and the
spans the code creates are no-ops.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Sequence
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult

TRACE_FILE_ENV = "PATTERNLY_TRACE_FILE"

tracer = trace.get_tracer("patternly")


def span_record(span: ReadableSpan) -> dict:
    """One finished span as a flat dict (one line of the trace file)."""
    ctx = span.get_span_context()
    return {
        "name": span.name,
        "trace_id": format(ctx.trace_id, "032x"),
        "span_id": format(ctx.span_id, "016x"),
        "parent_id": format(span.parent.span_id, "016x") if span.parent else None,
        "start_ns": span.start_time,
        "duration_ms": (span.end_time - span.start_time) / 1e6,
        "status": span.status.status_code.name,
        "attributes": dict(span.attributes or {}),
    }


class JsonlExporter(SpanExporter):
    """Appends each finished span to a file as one JSON object per line."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        lines = "".join(json.dumps(span_record(s), default=str) + "\n" for s in spans)
        try:
            with self._lock, self.path.open("a", encoding="utf-8") as f:
                f.write(lines)
        except OSError:
            return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS


def setup(service_name: str, trace_file: str | None = None) -> TracerProvider | None:
    """Install a tracer provider if a trace file or OTLP endpoint is configured. Returns it, or None if off."""
    trace_file = trace_file or os.environ.get(TRACE_FILE_ENV)
    otlp = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    if not trace_file and not otlp:
        return None
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if trace_file:
        provider.add_span_processor(BatchSpanProcessor(JsonlExporter(trace_file)))
    if otlp:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    return provider
