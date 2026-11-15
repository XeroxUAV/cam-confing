"""Unit tests for ``ConfigService`` using an in-memory repository stub."""

import pytest

from real_time_cam.application.config_service import ConfigService
from real_time_cam.domain.entities import (
    RESOLUTION_960X600,
    RESOLUTION_1920X1200,
    BackendRuntimeConfig,
    EncoderKind,
    StreamConfig,
)
from real_time_cam.domain.errors import ConfigPersistenceError, InvalidStreamConfigError

CUSTOM_FPS_HZ: int = 25
CUSTOM_BITRATE_KBPS: int = 3500


class InMemoryConfigRepository:
    """In-memory test double for ``ConfigRepositoryPort``."""

    def __init__(self, should_fail_save: bool = False) -> None:
        self.stored_config: BackendRuntimeConfig = BackendRuntimeConfig()
        self.should_fail_save = should_fail_save
        self.save_count: int = 0

    def load_or_create_default(self) -> BackendRuntimeConfig:
        return self.stored_config

    def save(self, config: BackendRuntimeConfig) -> None:
        if self.should_fail_save:
            msg = "Simulated disk full error"
            raise ConfigPersistenceError(msg)
        self.stored_config = config
        self.save_count += 1


def test_config_service_applies_and_resets_stream_config() -> None:
    """Verify apply_stream_config persists new stream settings and reset restores."""
    repo = InMemoryConfigRepository()
    service = ConfigService(repository=repo)

    updated = StreamConfig(
        resolution=RESOLUTION_1920X1200,
        fps_hz=CUSTOM_FPS_HZ,
        bitrate_kbps=CUSTOM_BITRATE_KBPS,
        encoder_kind=EncoderKind.SOFTWARE_X264,
    )
    service.apply_stream_config(updated)

    assert service.get_stream_config() == updated
    assert repo.stored_config.stream == updated

    service.reset_stream_to_default()
    assert service.get_stream_config().resolution == RESOLUTION_960X600


def test_config_service_keeps_previous_state_when_save_fails() -> None:
    """Verify in-memory state does not drift from storage when save raises."""
    repo = InMemoryConfigRepository(should_fail_save=True)
    service = ConfigService(repository=repo)
    initial_stream = service.get_stream_config()

    candidate = StreamConfig(resolution=RESOLUTION_1920X1200)
    with pytest.raises(ConfigPersistenceError, match="Simulated disk full"):
        service.apply_stream_config(candidate)

    assert service.get_stream_config() == initial_stream


def test_config_service_rejects_pi4_incompatible_v4l2_resolution() -> None:
    """Verify ConfigService rejects 1920x1200 paired with hardware_v4l2."""
    repo = InMemoryConfigRepository()
    service = ConfigService(repository=repo)

    incompatible = StreamConfig(
        resolution=RESOLUTION_1920X1200,
        encoder_kind=EncoderKind.HARDWARE_V4L2,
    )
    with pytest.raises(InvalidStreamConfigError):
        service.apply_stream_config(incompatible)
    assert repo.save_count == 0
