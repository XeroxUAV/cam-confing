"""Immutable domain entities for camera stream configuration and benchmarks."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from real_time_cam.domain.constants import (
    DEFAULT_BACKEND_HOST,
    DEFAULT_BACKEND_HTTP_PORT,
    DEFAULT_BITRATE_KBPS,
    DEFAULT_FPS_HZ,
    DEFAULT_MEDIAMTX_RTSP_PORT,
    DEFAULT_MEDIAMTX_WEBRTC_HTTP_PORT,
    DEFAULT_STREAM_PATH,
    HEIGHT_HIGH_PX,
    HEIGHT_LOW_PX,
    KEYFRAME_INTERVAL_S,
    MAX_BITRATE_KBPS,
    MAX_FPS_HZ,
    MAX_VALID_PORT,
    MIN_BITRATE_KBPS,
    MIN_FPS_HZ,
    MIN_KEYFRAME_INTERVAL_FRAMES,
    MIN_VALID_PORT,
    PI4_H264_LEVEL_4_MAX_HEIGHT_PX,
    WIDTH_HIGH_PX,
    WIDTH_LOW_PX,
)
from real_time_cam.domain.errors import InvalidEndpointError, InvalidStreamConfigError


class EncoderKind(StrEnum):
    """Supported H.264 encoder implementations on the Raspberry Pi 4."""

    SOFTWARE_X264 = "software_x264"
    HARDWARE_V4L2 = "hardware_v4l2"


DEFAULT_ENCODER_KIND: Final[EncoderKind] = EncoderKind.SOFTWARE_X264


@dataclass(frozen=True, slots=True)
class FrameResolution:
    """Video frame dimensions in pixels (`width_px` by `height_px`)."""

    width_px: int
    height_px: int

    def get_label(self) -> str:
        """Return compact ``WIDTHxHEIGHT`` text representation."""
        return f"{self.width_px}x{self.height_px}"


RESOLUTION_960X600: Final[FrameResolution] = FrameResolution(
    width_px=WIDTH_LOW_PX,
    height_px=HEIGHT_LOW_PX,
)
RESOLUTION_1920X1200: Final[FrameResolution] = FrameResolution(
    width_px=WIDTH_HIGH_PX,
    height_px=HEIGHT_HIGH_PX,
)
SUPPORTED_CAMERA_RESOLUTIONS: Final[tuple[FrameResolution, ...]] = (
    RESOLUTION_960X600,
    RESOLUTION_1920X1200,
)


def parse_frame_resolution(label: str) -> FrameResolution:
    """Resolve a ``WIDTHxHEIGHT`` label into a supported Arducam B0495 resolution.

    Args:
        label: Resolution text such as ``"960x600"`` or ``"1920x1200"``.

    Returns:
        Matching ``FrameResolution`` instance.

    Raises:
        InvalidStreamConfigError: If ``label`` is not supported by the B0495 camera.
    """
    normalized_label = label.strip().lower()
    for candidate in SUPPORTED_CAMERA_RESOLUTIONS:
        if candidate.get_label() == normalized_label:
            return candidate
    allowed_text = ", ".join(res.get_label() for res in SUPPORTED_CAMERA_RESOLUTIONS)
    msg = f"Unsupported resolution '{label}'. Allowed: {allowed_text}."
    raise InvalidStreamConfigError(msg)


@dataclass(frozen=True, slots=True)
class StreamConfig:
    """Validated live camera encoding configuration.

    Attributes:
        resolution: Frame size in pixels (must be supported by Arducam B0495).
        fps_hz: Target output frame rate in Hertz (frames per second).
        bitrate_kbps: Target H.264 encoder bitrate in kilobits per second.
        encoder_kind: Selected H.264 encoder strategy.
    """

    resolution: FrameResolution = RESOLUTION_960X600
    fps_hz: int = DEFAULT_FPS_HZ
    bitrate_kbps: int = DEFAULT_BITRATE_KBPS
    encoder_kind: EncoderKind = DEFAULT_ENCODER_KIND

    def __post_init__(self) -> None:
        """Enforce Arducam B0495 resolution and safe streaming bounds."""
        if self.resolution not in SUPPORTED_CAMERA_RESOLUTIONS:
            msg = f"Unsupported camera resolution: {self.resolution.get_label()}."
            raise InvalidStreamConfigError(msg)
        if not (MIN_FPS_HZ <= self.fps_hz <= MAX_FPS_HZ):
            msg = f"fps_hz ({self.fps_hz}) must be in [{MIN_FPS_HZ}, {MAX_FPS_HZ}]."
            raise InvalidStreamConfigError(msg)
        if not (MIN_BITRATE_KBPS <= self.bitrate_kbps <= MAX_BITRATE_KBPS):
            msg = (
                f"bitrate_kbps ({self.bitrate_kbps}) must be in "
                f"[{MIN_BITRATE_KBPS}, {MAX_BITRATE_KBPS}]."
            )
            raise InvalidStreamConfigError(msg)

    def compute_keyframe_interval_frames(self) -> int:
        """Compute IDR keyframe interval in frames for sub-second stream recovery."""
        return max(MIN_KEYFRAME_INTERVAL_FRAMES, self.fps_hz * KEYFRAME_INTERVAL_S)

    def validate_pi4_live_compatibility(self) -> None:
        """Reject encoder/resolution pairs unsupported by Raspberry Pi 4 silicon.

        Raises:
            InvalidStreamConfigError: If ``hardware_v4l2`` exceeds 1080p height.
        """
        is_v4l2 = self.encoder_kind == EncoderKind.HARDWARE_V4L2
        if is_v4l2 and self.resolution.height_px > PI4_H264_LEVEL_4_MAX_HEIGHT_PX:
            msg = (
                f"hardware_v4l2 on Raspberry Pi 4 supports heights up to "
                f"{PI4_H264_LEVEL_4_MAX_HEIGHT_PX} px; use software_x264 for "
                f"{self.resolution.get_label()}."
            )
            raise InvalidStreamConfigError(msg)


def _validate_required_host(host: str, field_label: str) -> None:
    """Ensure a hostname or bind address is non-empty and free of spaces or slashes."""
    cleaned_host = host.strip()
    if not cleaned_host or "/" in cleaned_host or " " in cleaned_host:
        msg = f"Invalid {field_label}: '{host}'."
        raise InvalidEndpointError(msg)


def _validate_port_number(port: int, field_label: str) -> None:
    """Ensure a TCP/UDP port number lies within ``[1, 65535]``."""
    if not (MIN_VALID_PORT <= port <= MAX_VALID_PORT):
        msg = f"Invalid {field_label}: {port}."
        raise InvalidEndpointError(msg)


@dataclass(frozen=True, slots=True)
class RtspPublishEndpoint:
    """Target MediaMTX RTSP ingestion endpoint (never hardcoded in source).

    Attributes:
        host: Hostname or IP address of the laptop running MediaMTX.
        port: TCP port of MediaMTX RTSP listener.
        stream_path: MediaMTX path name without leading slash.
    """

    host: str
    port: int = DEFAULT_MEDIAMTX_RTSP_PORT
    stream_path: str = DEFAULT_STREAM_PATH

    def __post_init__(self) -> None:
        """Validate host, port range, and non-empty stream path."""
        _validate_required_host(self.host, "MediaMTX host")
        _validate_port_number(self.port, "RTSP port")
        if not self.stream_path.strip().strip("/"):
            msg = "MediaMTX stream_path must not be empty."
            raise InvalidEndpointError(msg)

    def build_rtsp_url(self) -> str:
        """Format full ``rtsp://host:port/path`` URL."""
        cleaned_host = self.host.strip()
        cleaned_path = self.stream_path.strip().strip("/")
        return f"rtsp://{cleaned_host}:{self.port}/{cleaned_path}"


@dataclass(frozen=True, slots=True)
class BackendServerSettings:
    """HTTP bind settings for the FastAPI ground-control backend server."""

    host: str = DEFAULT_BACKEND_HOST
    port: int = DEFAULT_BACKEND_HTTP_PORT

    def __post_init__(self) -> None:
        """Validate bind host and HTTP port range."""
        _validate_required_host(self.host, "backend host")
        _validate_port_number(self.port, "backend HTTP port")


@dataclass(frozen=True, slots=True)
class MediaMtxSettings:
    """MediaMTX ports and stream path advertised by the backend.

    Attributes:
        public_host: Optional explicit hostname for MediaMTX; empty string means
            MediaMTX runs on the same host as the backend web server.
        rtsp_port: MediaMTX RTSP ingestion TCP port.
        webrtc_http_port: MediaMTX WebRTC/WHEP HTTP port.
        stream_path: MediaMTX stream path name (e.g. ``"cam"``).
    """

    public_host: str = ""
    rtsp_port: int = DEFAULT_MEDIAMTX_RTSP_PORT
    webrtc_http_port: int = DEFAULT_MEDIAMTX_WEBRTC_HTTP_PORT
    stream_path: str = DEFAULT_STREAM_PATH

    def __post_init__(self) -> None:
        """Validate optional public host, MediaMTX ports, and stream path."""
        if self.public_host.strip():
            _validate_required_host(self.public_host, "MediaMTX public_host")
        _validate_port_number(self.rtsp_port, "MediaMTX rtsp_port")
        _validate_port_number(self.webrtc_http_port, "MediaMTX webrtc_http_port")
        if not self.get_clean_stream_path():
            msg = "MediaMTX stream_path must not be empty."
            raise InvalidEndpointError(msg)

    def get_clean_stream_path(self) -> str:
        """Return trimmed stream path without leading or trailing slashes."""
        return self.stream_path.strip().strip("/")

    def build_whep_path(self) -> str:
        """Return normalized WHEP HTTP path such as ``"/cam/whep"``."""
        return f"/{self.get_clean_stream_path()}/whep"


@dataclass(frozen=True, slots=True)
class BackendRuntimeConfig:
    """Complete immutable runtime configuration persisted by the backend."""

    server: BackendServerSettings = BackendServerSettings()
    mediamtx: MediaMtxSettings = MediaMtxSettings()
    stream: StreamConfig = StreamConfig()

    def __post_init__(self) -> None:
        """Ensure persisted live stream settings are valid on Pi 4 hardware."""
        self.stream.validate_pi4_live_compatibility()


@dataclass(frozen=True, slots=True)
class EncoderBenchmarkResult:
    """Summary metrics from a single Raspberry Pi H.264 encoder benchmark run."""

    resolution_label: str
    encoder_kind: EncoderKind
    is_stable: bool
    mean_cpu_percent: float
    peak_temp_celsius: float
    achieved_fps_hz: float
    startup_latency_ms: float
    note: str
