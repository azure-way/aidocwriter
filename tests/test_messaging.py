from __future__ import annotations

import json

from docwriter.messaging import _json_fallback, _sanitize_queue_payload


def test_sanitize_queue_payload_drops_internal_and_callables() -> None:
    payload = {
        "job_id": "j1",
        "_renew_lock": lambda: None,
        "nested": {
            "ok": 1,
            "_internal": "x",
            "fn": lambda: None,
        },
        "items": [1, lambda: None, {"_tmp": 2, "keep": 3}],
    }

    safe = _sanitize_queue_payload(payload)

    assert "_renew_lock" not in safe
    assert safe["job_id"] == "j1"
    assert safe["nested"] == {"ok": 1}
    assert safe["items"] == [1, {"keep": 3}]


def test_json_fallback_handles_non_serializable_values() -> None:
    payload = {"obj": object(), "fn": lambda: None}
    dumped = json.dumps(payload, default=_json_fallback)
    assert "obj" in dumped
    assert '"fn": null' in dumped
