"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI  # type: ignore[import-not-found]

from admitpilot.api.routes.health import build_health_router
from admitpilot.app import AdmitPilotApplication, build_application
from admitpilot.config import AdmitPilotSettings, load_settings


def create_api_app(
    settings: AdmitPilotSettings | None = None,
    application: AdmitPilotApplication | None = None,
) -> FastAPI:
    """Create the HTTP API app."""

    effective_settings = settings or (
        application.settings if application is not None else load_settings()
    )
    effective_application = application or build_application(settings=effective_settings)
    api_app = FastAPI(title="AdmitPilot API", version="0.1.0")
    api_app.state.settings = effective_settings
    api_app.state.application = effective_application
    api_app.include_router(build_health_router(settings=effective_settings))
    return api_app


app = create_api_app()
