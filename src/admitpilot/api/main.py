"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from admitpilot.api.routes.health import build_health_router
from admitpilot.api.routes.v1 import build_v1_router
from admitpilot.api.store import DemoApiStore
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
    api_app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api_app.state.settings = effective_settings
    api_app.state.application = effective_application
    api_app.state.api_store = DemoApiStore(settings=effective_settings)
    api_app.include_router(build_health_router(settings=effective_settings))
    api_app.include_router(
        build_v1_router(
            application=effective_application,
            store=api_app.state.api_store,
        )
    )
    return api_app


app = create_api_app()
