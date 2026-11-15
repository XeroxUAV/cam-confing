"""Unit tests for ``TomlConfigRepository`` and Pydantic V2 TOML validation."""

from dataclasses import replace
from pathlib import Path

import pytest

from real_time_cam.domain.entities import (
    RESOLUTION_1920X1200,
    BackendRuntimeConfig,
    StreamConfig,
)
from real_time_cam.domain.errors import ConfigPersistenceError
from real_time_cam.infrastructure.persistence.toml_config_repository import (
    TomlConfigRepository,
)

SAVED_BITRATE_KBPS: int = 4200


def test_toml_repository_creates_default_and_round_trips_updates(
    tmp_path: Path,
) -> None:
    """Verify missing TOML file is created with defaults and round-trips edits."""
    config_file = tmp_path / "configs" / "backend.toml"
    repo = TomlConfigRepository(config_path=config_file)

    assert repo.config_path == config_file
    loaded_default = repo.load_or_create_default()
    assert config_file.is_file()
    assert loaded_default == BackendRuntimeConfig()

    updated = replace(
        loaded_default,
        stream=StreamConfig(
            resolution=RESOLUTION_1920X1200,
            bitrate_kbps=SAVED_BITRATE_KBPS,
        ),
    )
    repo.save(updated)

    reloaded = repo.load_or_create_default()
    assert reloaded == updated


@pytest.mark.parametrize(
    "invalid_toml_content",
    [
        "not = [valid toml",
        "[stream]\nunknown_typo_key = 123\n",
        '[stream]\nresolution = "1280x720"\n',
        '[stream]\nresolution = "1920x1200"\nencoder_kind = "hardware_v4l2"\n',
        '[server]\nhost = "bad/host"\n',
    ],
)
def test_toml_repository_rejects_corrupt_or_invalid_files(
    tmp_path: Path,
    invalid_toml_content: str,
) -> None:
    """Verify syntax errors, unknown keys, and domain violations raise cleanly."""
    config_file = tmp_path / "backend.toml"
    config_file.write_text(invalid_toml_content, encoding="utf-8")
    repo = TomlConfigRepository(config_path=config_file)

    with pytest.raises(ConfigPersistenceError):
        repo.load_or_create_default()


def test_toml_repository_wraps_os_write_error(tmp_path: Path) -> None:
    """Verify OSError during atomic write raises ConfigPersistenceError."""
    blocker_file = tmp_path / "not_a_dir"
    blocker_file.write_text("x", encoding="utf-8")
    repo = TomlConfigRepository(config_path=blocker_file / "backend.toml")

    with pytest.raises(ConfigPersistenceError, match="Failed to write config file"):
        repo.save(BackendRuntimeConfig())
