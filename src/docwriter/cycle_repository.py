from __future__ import annotations

import json
from typing import Any, Mapping, MutableMapping, Optional

from .telemetry import track_exception
from .stages.cycles import CycleState

try:
    from .status_store import get_status_table_store
except Exception:  # pragma: no cover
    get_status_table_store = None  # type: ignore[assignment]


_CYCLE_FIELDS = ("cycles", "expected_cycles", "cycles_completed", "cycles_remaining")


def _coerce_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def _extract_cycle_sources(raw: Any) -> list[Mapping[str, Any]]:
    sources: list[Mapping[str, Any]] = []
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


class CycleMetadataRepository:
    """Load and hydrate cycle metadata from persistent stores."""

    def __init__(self, store_factory=get_status_table_store):
        self._store_factory = store_factory
        self._store = None

    def _get_store(self):
        if not self._store_factory:
            return None
        if self._store is None:
            try:
                self._store = self._store_factory()
            except Exception as exc:  # pragma: no cover - telemetry only
                track_exception(exc, {"operation": "cycle_repo_get_store"})
                self._store_factory = None
                return None
        return self._store

    def hydrate(self, target: MutableMapping[str, Any], job_id: str) -> bool:
        if not job_id:
            return False
        store = self._get_store()
        if store is None:
            return False

        populated = False
        try:
            latest = store.latest(job_id)
        except Exception as exc:
            track_exception(exc, {"job_id": job_id, "operation": "cycle_repo_latest"})
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
            track_exception(exc, {"job_id": job_id, "operation": "cycle_repo_timeline"})
            history = []

        for entity in reversed(history):
            if not isinstance(entity, Mapping):
                continue
            _ingest(entity)
            if populated:
                break
        return populated


_default_repository: Optional[CycleMetadataRepository] = None


def get_cycle_repository() -> CycleMetadataRepository:
    global _default_repository
    if _default_repository is None:
        _default_repository = CycleMetadataRepository()
    return _default_repository


def ensure_cycle_state(
    payload: MutableMapping[str, Any],
    *,
    repository: Optional[CycleMetadataRepository] = None,
) -> CycleState:
    """
    Hydrate cycle metadata from persistent storage (if available), apply defaults, and return the CycleState.
    """
    repo = repository or get_cycle_repository()
    job_id = payload.get("job_id")
    if isinstance(job_id, str) and job_id:
        repo.hydrate(payload, job_id)
    cycle_state = CycleState.from_context(payload)
    cycle_state.apply(payload)
    return cycle_state
