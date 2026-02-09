from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI, Header

app = FastAPI(title="Sample MCP Server", version="0.1.0")


def _sample_profile() -> Dict[str, Any]:
    return {
        "company_name": "Acme Integration Group",
        "overview": "Azure-first systems integrator specializing in regulated industries.",
        "capabilities": [
            "Azure integration architecture",
            "API management",
            "Event-driven platforms",
        ],
        "industries": ["Finance", "Healthcare", "Retail"],
        "certifications": ["ISO 27001", "SOC 2 Type II"],
        "locations": ["Warsaw", "London", "Remote"],
        "references": [
            {
                "title": "Global bank integration program",
                "summary": "Designed and delivered a multi-region API + event backbone.",
                "outcome": "30% faster integration delivery",
                "year": "2024",
            }
        ],
    }


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/resources")
def list_resources(authorization: str | None = Header(default=None)) -> Dict[str, List[Dict[str, str]]]:
    return {
        "resources": [
            {
                "name": "company.profile",
                "path": "resources/company.profile",
                "description": "Structured company profile details.",
            }
        ]
    }


@app.get("/tools")
def list_tools(authorization: str | None = Header(default=None)) -> Dict[str, List[Dict[str, str]]]:
    return {
        "tools": [
            {
                "name": "company.query",
                "path": "tools/company.query",
                "description": "Query company capabilities and references.",
            }
        ]
    }


@app.get("/resources/company.profile")
def company_profile(authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    return _sample_profile()


@app.post("/tools/company.query")
def company_query(payload: Dict[str, Any], authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    query = str(payload.get("query") or "").strip()
    data = _sample_profile()
    if query:
        data["notes"] = f"Query received: {query}"
    return data
