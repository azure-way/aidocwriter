from __future__ import annotations

import azure.functions as func

from docwriter.queue import process_review
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
