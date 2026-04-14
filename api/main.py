"""
Gregor Zwanzig Core API — Python FastAPI Wrapper.

Exposes the Python core as HTTP endpoints for the Go API to proxy.
Runs on localhost:8000 (internal only).
"""
from fastapi import FastAPI

from api.routers import config, forecast, gpx, health

app = FastAPI(title="Gregor Zwanzig Core API", version="0.1.0")
app.include_router(health.router)
app.include_router(config.router)
app.include_router(forecast.router)
app.include_router(gpx.router)
