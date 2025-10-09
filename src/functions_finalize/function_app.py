from __future__ import annotations

import azure.functions as func

from docwriter.queue import process_finalize
from functions_shared.runtime import service_bus_handler

app = func.FunctionApp()


@app.function_name(name="finalize_trigger")
@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="%SERVICE_BUS_QUEUE_FINALIZE%",
    connection="SERVICE_BUS_CONNECTION_STRING",
)
def finalize_trigger(msg: func.ServiceBusMessage) -> None:
    service_bus_handler("worker-finalize", msg, process_finalize)
