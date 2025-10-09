from __future__ import annotations

import azure.functions as func

from docwriter.queue import process_verify
from functions_shared.runtime import service_bus_handler

app = func.FunctionApp()


@app.function_name(name="verify_trigger")
@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="%SERVICE_BUS_QUEUE_VERIFY%",
    connection="SERVICE_BUS_CONNECTION_STRING",
)
def verify_trigger(msg: func.ServiceBusMessage) -> None:
    service_bus_handler("worker-verify", msg, process_verify)
