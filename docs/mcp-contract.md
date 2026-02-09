# MCP Contract: Company Profile

DocWriter expects MCP servers to expose the following HTTP endpoints:

## Health
- `GET /healthz` → `{"status": "ok"}`
- `GET /health` → `{"status": "ok"}`

## Discovery
- `GET /resources`
  - Response:
    ```json
    {
      "resources": [
        { "name": "company.profile", "path": "resources/company.profile", "description": "..." }
      ]
    }
    ```
- `GET /tools`
  - Response:
    ```json
    {
      "tools": [
        { "name": "company.query", "path": "tools/company.query", "description": "..." }
      ]
    }
    ```

## Resource: Company Profile
- `GET /resources/company.profile`
- Response (schema):
  ```json
  {
    "company_name": "string",
    "overview": "string",
    "capabilities": ["string"],
    "industries": ["string"],
    "certifications": ["string"],
    "locations": ["string"],
    "references": [
      { "title": "string", "summary": "string", "outcome": "string", "year": "string" }
    ]
  }
  ```

## Tool: Company Query
- `POST /tools/company.query`
- Request:
  ```json
  { "query": "string" }
  ```
- Response: same schema as company profile, with optional `notes`.

## Authentication
- DocWriter will send the IDP access token as `Authorization: Bearer <token>`.
- MCP servers should validate tokens according to their own policies.
