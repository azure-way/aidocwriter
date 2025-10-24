from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, Optional


def coerce_int(value: Any, default: int = 0) -> int:
    """Best-effort conversion of arbitrary values to int with sensible default."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
