"""Pydantic V2 boundary schemas for persisted TOML backend configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from real_time_cam.domain.constants import (
    DEFAULT_BACKEND_HOST,
    DEFAULT_BACKEND_HTTP_PORT,
    DEFAULT_BITRATE_KBPS,
    DEFAULT_FPS_HZ,
    DEFAULT_MEDIAMTX_RTSP_PORT,
    DEFAULT_MEDIAMTX_WEBRTC_HTTP_PORT,
    DEFAULT_STREAM_PATH,
    MAX_BITRATE_KBPS,
    MAX_FPS_HZ,
    MAX_VALID_PORT,
    MIN_BITRATE_KBPS,
    MIN_FPS_HZ,
    MIN_VALID_PORT,
)
from real_time_cam.domain.entities import (
    DEFAULT_ENCODER_KIND,
    RESOLUTION_960X600,
    BackendRuntimeConfig,
    BackendServerSettings,
    EncoderKind,
    MediaMtxSettings,
    StreamConfig,
    parse_frame_resolution,
)
from real_time_cam.domain.errors import DomainError


class ServerSectionSchema(BaseModel):
    """Pydantic V2 schema for the ``[server]`` section of ``backend.toml``."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    host: str = Field(default=DEFAULT_BACKEND_HOST, min_length=1)
    port: int = Field(
        default=DEFAULT_BACKEND_HTTP_PORT,
        ge=MIN_VALID_PORT,
        le=MAX_VALID_PORT,
    )

    def to_domain(self) -> BackendServerSettings:
        """Convert validated schema into pure domain ``BackendServerSettings``."""
        return BackendServerSettings(host=self.host, port=self.port)


class MediaMtxSectionSchema(BaseModel):
    """Pydantic V2 schema for the ``[mediamtx]`` section of ``backend.toml``."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    public_host: str = Field(default="")
    rtsp_port: int = Field(
        default=DEFAULT_MEDIAMTX_RTSP_PORT,
        ge=MIN_VALID_PORT,
        le=MAX_VALID_PORT,
    )
    webrtc_http_port: int = Field(
        default=DEFAULT_MEDIAMTX_WEBRTC_HTTP_PORT,
        ge=MIN_VALID_PORT,
        le=MAX_VALID_PORT,
    )
    stream_path: str = Field(default=DEFAULT_STREAM_PATH, min_length=1)

    def to_domain(self) -> MediaMtxSettings:
        """Convert validated schema into pure domain ``MediaMtxSettings``."""
        return MediaMtxSettings(
            public_host=self.public_host,
            rtsp_port=self.rtsp_port,
            webrtc_http_port=self.webrtc_http_port,
            stream_path=self.stream_path,
        )


class StreamSectionSchema(BaseModel):
    """Pydantic V2 schema for the ``[stream]`` section and HTTP stream DTOs."""

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
    def _normalize_supported_resolution(cls, raw_label: str) -> str:
        """Validate ``WIDTHxHEIGHT`` against Arducam B0495 supported modes."""
        try:
            return parse_frame_resolution(raw_label).get_label()
        except DomainError as exc:
            raise ValueError(str(exc)) from exc

    @model_validator(mode="after")
    def _check_pi4_encoder_compatibility(self) -> StreamSectionSchema:
        """Enforce Pi 4 hardware encoder height limits at the Pydantic boundary."""
        try:
            self.to_domain().validate_pi4_live_compatibility()
        except DomainError as exc:
            raise ValueError(str(exc)) from exc
        return self

    def to_domain(self) -> StreamConfig:
        """Convert validated schema into pure domain ``StreamConfig``."""
        return StreamConfig(
            resolution=parse_frame_resolution(self.resolution),
            fps_hz=self.fps_hz,
            bitrate_kbps=self.bitrate_kbps,
            encoder_kind=self.encoder_kind,
        )

    @classmethod
    def from_domain(cls, stream: StreamConfig) -> StreamSectionSchema:
        """Construct boundary schema from pure domain ``StreamConfig``."""
        return cls(
            resolution=stream.resolution.get_label(),
            fps_hz=stream.fps_hz,
            bitrate_kbps=stream.bitrate_kbps,
            encoder_kind=stream.encoder_kind,
        )


class BackendConfigFileSchema(BaseModel):
    """Root Pydantic V2 schema for ``configs/backend.toml``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    server: ServerSectionSchema = Field(default_factory=ServerSectionSchema)
    mediamtx: MediaMtxSectionSchema = Field(default_factory=MediaMtxSectionSchema)
    stream: StreamSectionSchema = Field(default_factory=StreamSectionSchema)

    def to_domain(self) -> BackendRuntimeConfig:
        """Convert validated TOML schema tree into ``BackendRuntimeConfig``."""
        return BackendRuntimeConfig(
            server=self.server.to_domain(),
            mediamtx=self.mediamtx.to_domain(),
            stream=self.stream.to_domain(),
        )

    @classmethod
    def from_domain(cls, config: BackendRuntimeConfig) -> BackendConfigFileSchema:
        """Build root TOML schema tree from ``BackendRuntimeConfig``."""
        return cls(
            server=ServerSectionSchema(
                host=config.server.host,
                port=config.server.port,
            ),
            mediamtx=MediaMtxSectionSchema(
                public_host=config.mediamtx.public_host,
                rtsp_port=config.mediamtx.rtsp_port,
                webrtc_http_port=config.mediamtx.webrtc_http_port,
                stream_path=config.mediamtx.get_clean_stream_path(),
            ),
            stream=StreamSectionSchema.from_domain(config.stream),
        )
