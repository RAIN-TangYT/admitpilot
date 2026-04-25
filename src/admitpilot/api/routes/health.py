"""Health and readiness routes."""

from __future__ import annotations

from fastapi import APIRouter

from admitpilot.config import AdmitPilotSettings


def build_health_router(settings: AdmitPilotSettings) -> APIRouter:
    """Create the health router for the configured environment."""

    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "admitpilot",
            "mode": settings.run_mode,
        }

    @router.get("/ready")
    def ready() -> dict[str, str]:
        return {
            "status": "ready",
            "service": "admitpilot",
            "mode": settings.run_mode,
        }

    return router
