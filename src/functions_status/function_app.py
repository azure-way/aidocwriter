from __future__ import annotations

import json
import logging

import azure.functions as func

from docwriter.status_store import get_status_table_store

app = func.FunctionApp()


def _decode_message(message: func.ServiceBusMessage) -> dict[str, object]:
    try:
        body = message.get_body()
    except AttributeError:
        body = None
    if body is None:
        raw = str(message)
    else:
        try:
            raw = body.decode("utf-8")
        except AttributeError:
            raw = str(body)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logging.exception("Failed to decode status message: %s", raw)
        raise ValueError("Invalid status message payload") from exc


@app.function_name(name="status_topic_listener")
@app.service_bus_topic_trigger(
    arg_name="msg",
    topic_name="%SERVICE_BUS_TOPIC_STATUS%",
    subscription_name="%SERVICE_BUS_STATUS_SUBSCRIPTION%",
    connection="SERVICE_BUS_CONNECTION_STRING",
)
def status_topic_listener(msg: func.ServiceBusMessage) -> None:
    payload = _decode_message(msg)
    store = get_status_table_store()
    store.record(payload)
