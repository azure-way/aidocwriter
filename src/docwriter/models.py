from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(slots=True)
class StatusEvent:
    job_id: str
    stage: str
    ts: float
    message: str
    artifact: Optional[str] = None
    cycle: Optional[int] = None
    has_contradictions: Optional[bool] = None
    style_issues: Optional[bool] = None
    cohesion_issues: Optional[bool] = None
    placeholder_sections: Optional[bool] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "job_id": self.job_id,
            "stage": self.stage,
            "ts": self.ts,
            "message": self.message,
            "artifact": self.artifact,
            "cycle": self.cycle,
            "has_contradictions": self.has_contradictions,
            "style_issues": self.style_issues,
            "cohesion_issues": self.cohesion_issues,
            "placeholder_sections": self.placeholder_sections,
        }
        payload.update(self.extra)
        return {k: v for k, v in payload.items() if v is not None}
