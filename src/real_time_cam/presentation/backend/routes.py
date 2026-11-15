"""REST API route handlers delegating configuration use-cases to ``ConfigService``."""

from typing import Final

from fastapi import APIRouter, HTTPException, status

from real_time_cam.application.config_service import ConfigService
from real_time_cam.domain.errors import ConfigPersistenceError, InvalidStreamConfigError
from real_time_cam.presentation.backend.schemas import (
    ClientBootstrapDto,
    HealthResponseDto,
    StreamConfigDto,
)

API_V1_PREFIX: Final[str] = "/api/v1"


def build_api_router(config_service: ConfigService) -> APIRouter:
    """Create ``/api/v1`` router wired to ``config_service`` via closure DI."""
    router = APIRouter(prefix=API_V1_PREFIX, tags=["configuration"])

    @router.get("/health")
    async def get_health() -> HealthResponseDto:
        """Return lightweight liveness status."""
        return HealthResponseDto()

    @router.get("/config")
    async def get_bootstrap_config() -> ClientBootstrapDto:
        """Return MediaMTX playback settings, active stream config, and bounds."""
        return ClientBootstrapDto.from_domain(config_service.get_runtime_config())

    @router.get("/config/stream")
    async def get_stream_config() -> StreamConfigDto:
        """Return currently persisted camera stream encoding settings."""
        return StreamConfigDto.from_domain(config_service.get_stream_config())

    @router.put("/config/stream")
    async def put_stream_config(payload: StreamConfigDto) -> StreamConfigDto:
        """Validate and persist updated camera stream encoding settings."""
        _apply_or_raise_http_error(
            config_service=config_service,
            payload=payload,
        )
        return StreamConfigDto.from_domain(config_service.get_stream_config())

    @router.post("/config/stream/reset")
    async def reset_stream_config() -> StreamConfigDto:
        """Restore stream encoding settings to default ``960x600 @ 30 Hz``."""
        try:
            config_service.reset_stream_to_default()
        except ConfigPersistenceError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc
        return StreamConfigDto.from_domain(config_service.get_stream_config())

    return router


def _apply_or_raise_http_error(
    config_service: ConfigService,
    payload: StreamConfigDto,
) -> None:
    """Apply stream update and translate domain/persistence errors to HTTP codes."""
    try:
        config_service.apply_stream_config(payload.to_domain())
    except InvalidStreamConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except ConfigPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
