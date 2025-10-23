from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict

try:
    import azure.functions as func  # type: ignore
except Exception as exc:  # pragma: no cover - azure-functions only in runtime
    raise RuntimeError(
        "azure-functions package is required to run DocWriter Azure Functions"
    ) from exc

from docwriter import workers as worker_utils

Processor = Callable[[Dict[str, Any]], None]


def _decode_body(message: func.ServiceBusMessage) -> Dict[str, Any]:
    try:
        body = message.get_body()
    except AttributeError:
        body = None
    if body is not None:
        try:
            raw = body.decode("utf-8")
        except AttributeError:  # pragma: no cover - body may already be str
            raw = str(body)
    else:
        raw = str(message)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logging.exception("Unable to decode Service Bus message body: %s", raw)
        raise


def service_bus_handler(
    worker_name: str,
    message: func.ServiceBusMessage,
    processor: Processor,
) -> None:
    """Execute a queue processor inside an Azure Function host."""
    worker_utils.configure_logging(worker_name)
    data = _decode_body(message)
    try:
        processor(data)
    except Exception:
        logging.exception("Worker %s failed for job payload", worker_name)
        raise
