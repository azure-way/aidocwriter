FROM mcr.microsoft.com/azure-functions/python:4-python3.10

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    PYTHONUNBUFFERED=1

WORKDIR /workspace
COPY pyproject.toml README.md /workspace/
COPY src/docwriter /workspace/src/docwriter
RUN pip install --no-cache-dir /workspace

WORKDIR /home/site/wwwroot
COPY src/functions_shared ./functions_shared
COPY src/functions_finalize/function_app.py ./function_app.py
COPY src/functions_finalize/host.json ./host.json
