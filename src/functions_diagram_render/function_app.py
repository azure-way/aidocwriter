from __future__ import annotations

import azure.functions as func

from docwriter.diagram_renderer import process_diagram_render
from functions_shared.runtime import service_bus_handler

app = func.FunctionApp()


@app.function_name(name="diagram_render_trigger")
@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="%SERVICE_BUS_QUEUE_DIAGRAM_RENDER%",
    connection="SERVICE_BUS_CONNECTION_STRING",
)
def diagram_render_trigger(msg: func.ServiceBusMessage) -> None:
    service_bus_handler("diagram-render", msg, process_diagram_render)
