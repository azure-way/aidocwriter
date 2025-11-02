from __future__ import annotations

import azure.functions as func

from docwriter.stages.diagram_prep import process_diagram_prep
from functions_shared.runtime import service_bus_handler

app = func.FunctionApp()


@app.function_name(name="diagram_prep_trigger")
@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="%SERVICE_BUS_QUEUE_DIAGRAM_PREP%",
    connection="SERVICE_BUS_CONNECTION_STRING",
)
def diagram_prep_trigger(msg: func.ServiceBusMessage) -> None:
    service_bus_handler("diagram-prep", msg, process_diagram_prep)
