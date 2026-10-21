"""Sample consumer service for the GitHub Actions CI/CD platform.

A deliberately small FastAPI application used to exercise the reusable
workflows end to end: CI, security scanning, container builds, and
environment-gated deployments.
"""

import os

from fastapi import FastAPI

SERVICE_NAME = "sample-service"
SERVICE_VERSION = os.environ.get("SERVICE_VERSION", "0.1.0")

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)


@app.get("/")
def root() -> dict[str, str]:
    """Service identity endpoint."""
    return {"service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness/readiness probe used by containers and load balancers."""
    return {"status": "ok"}


@app.get("/greet/{name}")
def greet(name: str) -> dict[str, str]:
    """Trivial business-logic endpoint so tests cover a code path."""
    cleaned = name.strip()
    if not cleaned:
        cleaned = "world"
    return {"message": f"Hello, {cleaned}!"}
