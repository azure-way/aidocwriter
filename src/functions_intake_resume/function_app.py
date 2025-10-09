from __future__ import annotations

import azure.functions as func

from docwriter.queue import process_intake_resume
from functions_shared.runtime import service_bus_handler

app = func.FunctionApp()


@app.function_name(name="intake_resume_trigger")
@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="%SERVICE_BUS_QUEUE_INTAKE_RESUME%",
    connection="SERVICE_BUS_CONNECTION_STRING",
)
def intake_resume_trigger(msg: func.ServiceBusMessage) -> None:
    service_bus_handler("worker-intake-resume", msg, process_intake_resume)
