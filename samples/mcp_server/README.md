# Sample MCP Server (Company Profile)

This sample server demonstrates the MCP contract expected by DocWriter Studio.
It exposes:

- `GET /healthz` (health probe)
- `GET /resources` (resource listing)
- `GET /tools` (tool listing)
- `GET /resources/company.profile` (company profile resource)
- `POST /tools/company.query` (tool invocation)

Run locally:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn
uvicorn app:app --host 0.0.0.0 --port 8899
```

Example MCP config in the DocWriter UI:

- Base URL: `http://localhost:8899`
- Resource path: `resources/company.profile`
- Tool path: `tools/company.query`

The server accepts bearer tokens but does not validate them; implement your own
auth policy as needed.
