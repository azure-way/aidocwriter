from __future__ import annotations

import json
import threading
from typing import Dict, Optional

from docwriter.queue import _status  # type: ignore


class StatusStore:
    """In-memory capture of job status events.

    This provides a best-effort view for API consumers. For full fidelity,
    clients should monitor the Service Bus status topic directly.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: Dict[str, Dict] = {}

    def record(self, payload: Dict) -> None:
        job_id = payload.get("job_id")
        if not job_id:
            return
        with self._lock:
            self._latest[job_id] = payload

    def latest(self, job_id: str) -> Optional[Dict]:
        with self._lock:
            return self._latest.get(job_id)


status_store = StatusStore()
