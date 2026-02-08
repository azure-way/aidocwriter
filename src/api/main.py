from __future__ import annotations

from fastapi import FastAPI

from .routers import health, intake, jobs, profile

app = FastAPI(title="DocWriter API", version="0.1.0")

app.include_router(health.router)
app.include_router(intake.router)
app.include_router(jobs.router)
app.include_router(profile.router)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
