from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass
import logging
import os

try:
    from opentelemetry import trace  # type: ignore
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore
    from opentelemetry.sdk.resources import Resource  # type: ignore
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore
    from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore
except Exception:  # pragma: no cover
    trace = None

try:
    from applicationinsights import TelemetryClient  # type: ignore
except Exception:  # pragma: no cover
    TelemetryClient = None  # type: ignore

from .config import get_settings
from .storage import BlobStore, JobStoragePaths


_initialized = False
_telemetry_client: TelemetryClient | None = None


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


def get_telemetry_client() -> TelemetryClient | None:
    global _telemetry_client
    if _telemetry_client is not None:
        return _telemetry_client
    if TelemetryClient is None:
        _telemetry_client = None
        return _telemetry_client
    instrumentation_key = os.getenv("APPINSIGHTS_INSTRUMENTATION_KEY")
    if instrumentation_key:
        _telemetry_client = TelemetryClient(instrumentation_key)
    else:
        _telemetry_client = None
    return _telemetry_client


def track_event(name: str, properties: dict[str, str] | None = None) -> None:
    client = get_telemetry_client()
    if client:
        try:
            client.track_event(name, properties or {})
            client.flush()
        except Exception:
            logging.exception("Failed to send Application Insights event %s", name)


def track_exception(exc: BaseException, properties: dict[str, str] | None = None) -> None:
    client = get_telemetry_client()
    if client:
        try:
            client.track_exception(type(exc), exc, exc.__traceback__, properties or {})
            client.flush()
        except Exception:
            logging.exception("Failed to send Application Insights exception")


@dataclass
class StageTiming:
    job_id: str
    stage: str
    cycle: int | None
    start: float
    duration_s: float | None = None

    @property
    def elapsed_seconds(self) -> float:
        if self.duration_s is not None:
            return self.duration_s
        return max(0.0, time.perf_counter() - self.start)

    def complete(self, duration: float) -> None:
        self.duration_s = duration


@contextmanager
def stage_timer(
    job_id: str,
    stage: str,
    cycle: int | None = None,
    *,
    user_id: str | None = None,
) -> StageTiming:
    """Context manager to time a stage and upload metrics JSON to Blob."""
    settings = get_settings()
    init_tracer()
    tracer = trace.get_tracer("docwriter") if trace else None
    appinsights_client = get_telemetry_client()
    timing = StageTiming(job_id=job_id, stage=stage, cycle=cycle, start=time.perf_counter())
    span = None
    if tracer:
        span = tracer.start_span(name=f"stage:{stage}")
        span.set_attribute("job_id", job_id)
        if cycle is not None:
            span.set_attribute("cycle", cycle)
    props_base = {"job_id": job_id, "stage": stage}
    if cycle is not None:
        props_base["cycle"] = str(cycle)
    track_event("stage_started", props_base)
    try:
        yield timing
    except Exception as exc:
        if span:
            span.record_exception(exc)
        track_exception(exc, props_base)
        track_event("stage_failed", props_base)
        raise
    finally:
        duration_s = time.perf_counter() - timing.start
        timing.complete(duration_s)
        if span:
            span.set_attribute("duration_s", duration_s)
            span.end()
        props_completed = {**props_base, "duration_s": f"{duration_s:.4f}"}
        track_event("stage_completed", props_completed)
        # Best-effort metrics upload
        try:
            store = BlobStore()
            metrics = {"job_id": job_id, "stage": stage, "cycle": cycle, "duration_s": duration_s}
            if user_id:
                metrics["user_id"] = user_id
                blob = JobStoragePaths(user_id=user_id, job_id=job_id).metrics(
                    f"{stage}_{('cycle'+str(cycle)) if cycle else 'once'}.json"
                )
            else:
                blob = f"jobs/{job_id}/metrics/{stage}_{('cycle'+str(cycle)) if cycle else 'once'}.json"
            store.put_text(blob=blob, text=json.dumps(metrics, indent=2))
        except Exception:
            pass
