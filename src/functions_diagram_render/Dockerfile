FROM mcr.microsoft.com/azure-functions/python:4-python3.10

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends graphviz \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY pyproject.toml README.md /workspace/
COPY src/docwriter /workspace/src/docwriter
RUN pip install --no-cache-dir /workspace

WORKDIR /home/site/wwwroot
COPY src/functions_shared ./functions_shared
COPY src/functions_diagram_render/function_app.py ./function_app.py
COPY src/functions_diagram_render/host.json ./host.json
