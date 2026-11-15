"""Application service orchestrating validated runtime and stream configuration."""

from dataclasses import replace

from real_time_cam.domain.entities import BackendRuntimeConfig, StreamConfig
from real_time_cam.domain.ports import ConfigRepositoryPort


class ConfigService:
    """Manage active camera configuration backed by a persistent repository.

    Follows Command-Query Separation: ``get_*`` methods are pure queries and
    ``apply_*`` / ``reset_*`` methods mutate persisted and in-memory state.
    """

    def __init__(self, repository: ConfigRepositoryPort) -> None:
        """Initialize service and load (or create) default configuration."""
        self._repository = repository
        self._config: BackendRuntimeConfig = repository.load_or_create_default()

    def get_runtime_config(self) -> BackendRuntimeConfig:
        """Return the complete active runtime configuration."""
        return self._config

    def get_stream_config(self) -> StreamConfig:
        """Return the active camera stream encoding configuration."""
        return self._config.stream

    def apply_stream_config(self, new_stream: StreamConfig) -> None:
        """Validate, persist, and activate ``new_stream``.

        Args:
            new_stream: Candidate stream encoding configuration.

        Raises:
            InvalidStreamConfigError: If ``new_stream`` is incompatible with Pi 4.
            ConfigPersistenceError: If writing to persistent storage fails.
        """
        new_stream.validate_pi4_live_compatibility()
        updated_config = replace(self._config, stream=new_stream)
        self._repository.save(updated_config)
        self._config = updated_config

    def reset_stream_to_default(self) -> None:
        """Restore stream encoding settings to safe benchmark-verified defaults."""
        self.apply_stream_config(StreamConfig())
