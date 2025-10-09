from __future__ import annotations

import azure.functions as func

from docwriter.queue import process_rewrite
from functions_shared.runtime import service_bus_handler

app = func.FunctionApp()


@app.function_name(name="rewrite_trigger")
@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="%SERVICE_BUS_QUEUE_REWRITE%",
    connection="SERVICE_BUS_CONNECTION_STRING",
)
def rewrite_trigger(msg: func.ServiceBusMessage) -> None:
    service_bus_handler("worker-rewrite", msg, process_rewrite)
