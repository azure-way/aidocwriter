from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, List, Mapping, MutableMapping, Optional

from ..telemetry import track_exception

try:
    from ..status_store import get_status_table_store
except Exception:  # pragma: no cover
    get_status_table_store = None  # type: ignore[assignment]


def coerce_int(value: Any, default: int = 0) -> int:
    """Best-effort conversion of arbitrary values to int with sensible default."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class CycleState:
    requested: int
    completed: int

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> "CycleState":
        requested = coerce_int(
            context.get("cycles"),
            default=coerce_int(context.get("expected_cycles", 1)),
        )
        requested = max(1, requested)

        completed = coerce_int(context.get("cycles_completed", 0))
        completed = max(0, min(requested, completed))

        remaining_hint = context.get("cycles_remaining")
        if remaining_hint is not None:
            remaining = max(0, min(requested - completed, coerce_int(remaining_hint)))
            completed = min(requested, requested - remaining)

        return cls(requested=requested, completed=completed)

    @property
    def remaining(self) -> int:
        return max(0, self.requested - self.completed)

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0

    def consume_rewrite(self) -> "CycleState":
        if self.exhausted:
            return self
        new_completed = min(self.requested, self.completed + 1)
        return CycleState(self.requested, new_completed)

    def apply(self, target: MutableMapping[str, Any]) -> None:
        target["cycles"] = self.requested
        target["expected_cycles"] = self.requested
        target["cycles_completed"] = self.completed
        target["cycles_remaining"] = self.remaining


def enrich_details_with_cycles(
    details: Mapping[str, Any],
    source: Optional[Mapping[str, Any]],
    *,
    cycle_idx: Optional[int] = None,
) -> dict[str, Any]:
    enriched = dict(details)
    if source is not None:
        cycle_state = CycleState.from_context(source)
        enriched.setdefault("requested_cycles", cycle_state.requested)
        enriched.setdefault("expected_cycles", cycle_state.requested)
        enriched.setdefault("cycles_completed", cycle_state.completed)
        enriched.setdefault("cycles_remaining", cycle_state.remaining)
    if cycle_idx is not None:
        enriched.setdefault("cycle_index", cycle_idx)
    return enriched


_CYCLE_FIELDS = ("cycles", "expected_cycles", "cycles_completed", "cycles_remaining")


def _merge_cycles(target: MutableMapping[str, Any], source: Mapping[str, Any]) -> bool:
    updated = False
    for field in _CYCLE_FIELDS:
        if field not in source:
            continue
        value = _coerce_optional_int(source.get(field))
        if value is None:
            continue
        current = target.get(field)
        if current in (None, "", []):
            target[field] = value
            updated = True
    return updated


def _extract_cycle_sources(raw: Any) -> List[Mapping[str, Any]]:
    sources: List[Mapping[str, Any]] = []
    if isinstance(raw, Mapping):
        sources.append(raw)
    elif isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None
        if isinstance(parsed, Mapping):
            sources.append(parsed)
    return sources


def hydrate_cycle_metadata(target: MutableMapping[str, Any], *, job_id: str) -> bool:
    """
    Ensure the target mapping includes cycle information by consulting the status store.

    Returns True if any cycle field was populated.
    """
    if not job_id or get_status_table_store is None:
        return False
    try:
        store = get_status_table_store()
    except Exception as exc:  # pragma: no cover - telemetry only
        track_exception(exc, {"job_id": job_id, "operation": "hydrate_cycle_metadata"})
        return False

    populated = False
    try:
        latest = store.latest(job_id)
    except Exception as exc:
        track_exception(exc, {"job_id": job_id, "operation": "hydrate_cycle_metadata_latest"})
        latest = None

    def _ingest(entity: Mapping[str, Any]) -> None:
        nonlocal populated
        if _merge_cycles(target, entity):
            populated = True
        for source in _extract_cycle_sources(entity.get("details")):
            if _merge_cycles(target, source):
                populated = True
            nested = source.get("parsed_message")
            if isinstance(nested, Mapping) and _merge_cycles(target, nested):
                populated = True

    if latest:
        _ingest(latest)
        if populated:
            return True

    try:
        history = store.timeline(job_id)
    except Exception as exc:
        track_exception(exc, {"job_id": job_id, "operation": "hydrate_cycle_metadata_timeline"})
        history = []

    for entity in reversed(history):
        if not isinstance(entity, Mapping):
            continue
        _ingest(entity)
        if populated:
            break
    return populated


def ensure_cycle_state(payload: MutableMapping[str, Any]) -> CycleState:
    """
    Hydrate cycle metadata from the status store (if available), apply defaults, and return the CycleState.
    """
    job_id = payload.get("job_id")
    if isinstance(job_id, str) and job_id:
        try:
            hydrate_cycle_metadata(payload, job_id=job_id)
        except Exception as exc:  # pragma: no cover - defensive telemetry
            track_exception(exc, {"job_id": job_id, "operation": "ensure_cycle_state"})
    cycle_state = CycleState.from_context(payload)
    cycle_state.apply(payload)
    return cycle_state
