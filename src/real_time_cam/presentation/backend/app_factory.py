"""FastAPI application factory mounting REST routes and offline static web UI."""

from pathlib import Path
from typing import Final

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from real_time_cam.application.config_service import ConfigService
from real_time_cam.presentation.backend.routes import build_api_router

DEFAULT_WEB_ASSETS_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "web"


def create_backend_app(
    config_service: ConfigService,
    web_root: Path = DEFAULT_WEB_ASSETS_DIR,
) -> FastAPI:
    """Build FastAPI app with offline-safe settings, REST API, and static web UI.

    Swagger/ReDoc HTML views are disabled because their default templates pull
    scripts from external CDNs, violating the offline drone LAN requirement.
    The machine-readable schema remains available locally at ``/api/openapi.json``.
    """
    if not web_root.is_dir():
        msg = f"Static web directory does not exist: '{web_root}'"
        raise FileNotFoundError(msg)

    app = FastAPI(
        title="XeroxUAV Camera Configurator",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.include_router(build_api_router(config_service))
    app.mount("/", StaticFiles(directory=web_root, html=True), name="web-ui")
    return app
