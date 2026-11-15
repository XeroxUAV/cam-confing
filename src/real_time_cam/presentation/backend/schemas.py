"""Pydantic V2 HTTP request and response DTOs for the FastAPI backend."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from real_time_cam.domain.constants import (
    DEFAULT_BITRATE_KBPS,
    DEFAULT_FPS_HZ,
    MAX_BITRATE_KBPS,
    MAX_FPS_HZ,
    MIN_BITRATE_KBPS,
    MIN_FPS_HZ,
)
from real_time_cam.domain.entities import (
    DEFAULT_ENCODER_KIND,
    RESOLUTION_960X600,
    SUPPORTED_CAMERA_RESOLUTIONS,
    BackendRuntimeConfig,
    EncoderKind,
    MediaMtxSettings,
    StreamConfig,
    parse_frame_resolution,
)
from real_time_cam.domain.errors import DomainError


class HealthResponseDto(BaseModel):
    """Health-check payload confirming the FastAPI backend is reachable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ok"] = "ok"
    service: str = "real-time-cam-backend"


class IntBoundsDto(BaseModel):
    """Inclusive integer range ``[min_value, max_value]`` advertised to UI."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_value: int
    max_value: int


class StreamCapabilitiesDto(BaseModel):
    """Allowed camera resolutions, encoders, and slider bounds for the web UI."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    supported_resolutions: tuple[str, ...]
    supported_encoders: tuple[EncoderKind, ...]
    fps_bounds_hz: IntBoundsDto
    bitrate_bounds_kbps: IntBoundsDto

    @classmethod
    def build_default(cls) -> StreamCapabilitiesDto:
        """Construct capabilities metadata from pure domain constants."""
        return cls(
            supported_resolutions=tuple(
                res.get_label() for res in SUPPORTED_CAMERA_RESOLUTIONS
            ),
            supported_encoders=tuple(EncoderKind),
            fps_bounds_hz=IntBoundsDto(min_value=MIN_FPS_HZ, max_value=MAX_FPS_HZ),
            bitrate_bounds_kbps=IntBoundsDto(
                min_value=MIN_BITRATE_KBPS,
                max_value=MAX_BITRATE_KBPS,
            ),
        )


class MediaMtxPlaybackDto(BaseModel):
    """MediaMTX playback coordinates advertised to the browser WHEP client."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    public_host: str
    webrtc_http_port: int
    stream_path: str
    whep_path: str

    @classmethod
    def from_domain(cls, settings: MediaMtxSettings) -> MediaMtxPlaybackDto:
        """Build DTO from domain ``MediaMtxSettings``."""
        return cls(
            public_host=settings.public_host.strip(),
            webrtc_http_port=settings.webrtc_http_port,
            stream_path=settings.get_clean_stream_path(),
            whep_path=settings.build_whep_path(),
        )


class StreamConfigDto(BaseModel):
    """Validated HTTP JSON body / response representing ``StreamConfig``."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    resolution: str = Field(default=RESOLUTION_960X600.get_label())
    fps_hz: int = Field(default=DEFAULT_FPS_HZ, ge=MIN_FPS_HZ, le=MAX_FPS_HZ)
    bitrate_kbps: int = Field(
        default=DEFAULT_BITRATE_KBPS,
        ge=MIN_BITRATE_KBPS,
        le=MAX_BITRATE_KBPS,
    )
    encoder_kind: EncoderKind = Field(default=DEFAULT_ENCODER_KIND)

    @field_validator("resolution")
    @classmethod
    def _validate_resolution_label(cls, raw_label: str) -> str:
        """Reject resolutions not supported by the Arducam B0495 sensor."""
        try:
            return parse_frame_resolution(raw_label).get_label()
        except DomainError as exc:
            raise ValueError(str(exc)) from exc

    @model_validator(mode="after")
    def _validate_pi4_compatibility(self) -> StreamConfigDto:
        """Reject ``1920x1200`` paired with ``hardware_v4l2`` with HTTP 422."""
        try:
            self.to_domain().validate_pi4_live_compatibility()
        except DomainError as exc:
            raise ValueError(str(exc)) from exc
        return self

    def to_domain(self) -> StreamConfig:
        """Convert validated HTTP DTO into pure domain ``StreamConfig``."""
        return StreamConfig(
            resolution=parse_frame_resolution(self.resolution),
            fps_hz=self.fps_hz,
            bitrate_kbps=self.bitrate_kbps,
            encoder_kind=self.encoder_kind,
        )

    @classmethod
    def from_domain(cls, config: StreamConfig) -> StreamConfigDto:
        """Build HTTP DTO from pure domain ``StreamConfig``."""
        return cls(
            resolution=config.resolution.get_label(),
            fps_hz=config.fps_hz,
            bitrate_kbps=config.bitrate_kbps,
            encoder_kind=config.encoder_kind,
        )


class ClientBootstrapDto(BaseModel):
    """Combined initial state returned by ``GET /api/v1/config``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mediamtx: MediaMtxPlaybackDto
    stream: StreamConfigDto
    capabilities: StreamCapabilitiesDto

    @classmethod
    def from_domain(cls, runtime_config: BackendRuntimeConfig) -> ClientBootstrapDto:
        """Assemble bootstrap payload from ``BackendRuntimeConfig``."""
        return cls(
            mediamtx=MediaMtxPlaybackDto.from_domain(runtime_config.mediamtx),
            stream=StreamConfigDto.from_domain(runtime_config.stream),
            capabilities=StreamCapabilitiesDto.build_default(),
        )
