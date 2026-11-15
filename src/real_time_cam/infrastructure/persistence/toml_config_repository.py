"""TOML file adapter implementing ``ConfigRepositoryPort`` with atomic writes."""

import tomllib
from pathlib import Path

import tomli_w
from pydantic import ValidationError

from real_time_cam.domain.entities import BackendRuntimeConfig
from real_time_cam.domain.errors import ConfigPersistenceError, DomainError
from real_time_cam.infrastructure.persistence.config_models import (
    BackendConfigFileSchema,
)


class TomlConfigRepository:
    """Persist and validate ``BackendRuntimeConfig`` as a local TOML file."""

    def __init__(self, config_path: Path) -> None:
        """Initialize repository bound to ``config_path``."""
        self._config_path = config_path

    @property
    def config_path(self) -> Path:
        """Return target TOML file path."""
        return self._config_path

    def load_or_create_default(self) -> BackendRuntimeConfig:
        """Load validated TOML config, or write and return defaults if absent.

        Raises:
            ConfigPersistenceError: On I/O failure, invalid TOML syntax, or
                schema/domain validation errors.
        """
        if not self._config_path.exists():
            default_config = BackendRuntimeConfig()
            self.save(default_config)
            return default_config
        return self._read_and_validate()

    def save(self, config: BackendRuntimeConfig) -> None:
        """Serialize ``config`` to TOML and atomically replace target file.

        Raises:
            ConfigPersistenceError: If directory creation or atomic write fails.
        """
        schema = BackendConfigFileSchema.from_domain(config)
        toml_text = tomli_w.dumps(schema.model_dump(mode="json"))
        temp_path = self._config_path.with_suffix(".toml.tmp")
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(toml_text, encoding="utf-8")
            temp_path.replace(self._config_path)
        except OSError as exc:
            msg = f"Failed to write config file '{self._config_path}': {exc}"
            raise ConfigPersistenceError(msg) from exc

    def _read_and_validate(self) -> BackendRuntimeConfig:
        """Parse TOML text and validate through Pydantic V2 + domain rules."""
        try:
            raw_text = self._config_path.read_text(encoding="utf-8")
            parsed_toml = tomllib.loads(raw_text)
            schema = BackendConfigFileSchema.model_validate(parsed_toml)
            return schema.to_domain()
        except (OSError, tomllib.TOMLDecodeError, ValidationError, DomainError) as exc:
            msg = f"Invalid configuration in '{self._config_path}': {exc}"
            raise ConfigPersistenceError(msg) from exc
