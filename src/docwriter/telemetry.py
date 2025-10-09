from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass

try:
    from opentelemetry import trace  # type: ignore
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore
    from opentelemetry.sdk.resources import Resource  # type: ignore
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore
    from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore
except Exception:  # pragma: no cover
    trace = None

from .config import get_settings
from .storage import BlobStore


_initialized = False


def init_tracer():
    global _initialized
    if _initialized:
        return
    settings = get_settings()
    if trace is None or not settings.otlp_endpoint:
        _initialized = True
        return
    resource = Resource.create({"service.name": "docwriter"})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    _initialized = True


@contextmanager
def stage_timer(job_id: str, stage: str, cycle: int | None = None):
    """Context manager to time a stage and upload metrics JSON to Blob."""
    settings = get_settings()
    init_tracer()
    tracer = trace.get_tracer("docwriter") if trace else None
    start = time.perf_counter()
    span = None
    if tracer:
        span = tracer.start_span(name=f"stage:{stage}")
        span.set_attribute("job_id", job_id)
        if cycle is not None:
            span.set_attribute("cycle", cycle)
    try:
        yield
    finally:
        duration_s = time.perf_counter() - start
        if span:
            span.set_attribute("duration_s", duration_s)
            span.end()
        # Best-effort metrics upload
        try:
            store = BlobStore()
            metrics = {"job_id": job_id, "stage": stage, "cycle": cycle, "duration_s": duration_s}
            blob = f"jobs/{job_id}/metrics/{stage}_{('cycle'+str(cycle)) if cycle else 'once'}.json"
            store.put_text(blob=blob, text=json.dumps(metrics, indent=2))
        except Exception:
            pass

