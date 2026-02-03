from __future__ import annotations

import azure.functions as func

from docwriter.queue import (
    process_review,
    process_review_general,
    process_review_style,
    process_review_cohesion,
    process_review_summary,
)
from functions_shared.runtime import service_bus_handler

app = func.FunctionApp()


@app.function_name(name="review_trigger")
@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="%SERVICE_BUS_QUEUE_REVIEW%",
    connection="SERVICE_BUS_CONNECTION_STRING",
)
def review_trigger(msg: func.ServiceBusMessage) -> None:
    service_bus_handler("worker-review", msg, process_review)


@app.function_name(name="review_general_trigger")
@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="%SERVICE_BUS_QUEUE_REVIEW_GENERAL%",
    connection="SERVICE_BUS_CONNECTION_STRING",
)
def review_general_trigger(msg: func.ServiceBusMessage) -> None:
    service_bus_handler("worker-review-general", msg, process_review_general)


@app.function_name(name="review_style_trigger")
@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="%SERVICE_BUS_QUEUE_REVIEW_STYLE%",
    connection="SERVICE_BUS_CONNECTION_STRING",
)
def review_style_trigger(msg: func.ServiceBusMessage) -> None:
    service_bus_handler("worker-review-style", msg, process_review_style)


@app.function_name(name="review_cohesion_trigger")
@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="%SERVICE_BUS_QUEUE_REVIEW_COHESION%",
    connection="SERVICE_BUS_CONNECTION_STRING",
)
def review_cohesion_trigger(msg: func.ServiceBusMessage) -> None:
    service_bus_handler("worker-review-cohesion", msg, process_review_cohesion)


@app.function_name(name="review_summary_trigger")
@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="%SERVICE_BUS_QUEUE_REVIEW_SUMMARY%",
    connection="SERVICE_BUS_CONNECTION_STRING",
)
def review_summary_trigger(msg: func.ServiceBusMessage) -> None:
    service_bus_handler("worker-review-summary", msg, process_review_summary)
