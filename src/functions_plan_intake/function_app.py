from __future__ import annotations

import azure.functions as func

from docwriter.queue import process_plan_intake
from functions_shared.runtime import service_bus_handler

app = func.FunctionApp()


@app.function_name(name="plan_intake_trigger")
@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="%SERVICE_BUS_QUEUE_PLAN_INTAKE%",
    connection="SERVICE_BUS_CONNECTION_STRING",
)
def plan_intake_trigger(msg: func.ServiceBusMessage) -> None:
    service_bus_handler("worker-plan-intake", msg, process_plan_intake)
