"""Start the AdmitPilot FastAPI backend with environment settings."""

from __future__ import annotations

import sys
from pathlib import Path

import uvicorn

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from admitpilot.api.main import create_api_app  # noqa: E402
from admitpilot.app import build_application  # noqa: E402
from admitpilot.config import load_settings  # noqa: E402


def main() -> None:
    """Run the API server without requiring PYTHONPATH or uvicorn CLI flags."""

    settings = load_settings()
    application = build_application(settings=settings)
    api_app = create_api_app(settings=settings, application=application)
    uvicorn.run(
        api_app,
        host=settings.api_host or DEFAULT_HOST,
        port=settings.api_port or DEFAULT_PORT,
    )


if __name__ == "__main__":
    main()
