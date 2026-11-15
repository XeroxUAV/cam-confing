"""CLI composition root launching the FastAPI ground-control backend server."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import uvicorn

from real_time_cam.application.config_service import ConfigService
from real_time_cam.domain.constants import (
    DEFAULT_BACKEND_CONFIG_RELATIVE_PATH,
    MAX_VALID_PORT,
    MIN_VALID_PORT,
)
from real_time_cam.domain.errors import ConfigPersistenceError, InvalidEndpointError
from real_time_cam.infrastructure.persistence.toml_config_repository import (
    TomlConfigRepository,
)
from real_time_cam.presentation.backend.app_factory import create_backend_app


def build_argument_parser() -> argparse.ArgumentParser:
    """Build CLI parser for ``xerox-cam-backend``."""
    parser = argparse.ArgumentParser(
        prog="xerox-cam-backend",
        description="Run the XeroxUAV FastAPI camera configurator backend.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(DEFAULT_BACKEND_CONFIG_RELATIVE_PATH),
        help="Path to persisted TOML configuration file (created if absent).",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Optional bind host override (defaults to [server].host in TOML).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Optional HTTP port override (defaults to [server].port in TOML).",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Load/create and validate configuration, print summary, and exit.",
    )
    return parser


def _resolve_bind_target(
    configured_host: str,
    configured_port: int,
    override_host: str | None,
    override_port: int | None,
) -> tuple[str, int]:
    """Select CLI overrides when provided and validate resulting port."""
    bind_host = override_host.strip() if override_host is not None else configured_host
    bind_port = override_port if override_port is not None else configured_port
    if not bind_host or " " in bind_host or "/" in bind_host:
        msg = f"Invalid bind host: '{bind_host}'."
        raise InvalidEndpointError(msg)
    if not (MIN_VALID_PORT <= bind_port <= MAX_VALID_PORT):
        msg = f"Invalid bind port: {bind_port}."
        raise InvalidEndpointError(msg)
    return bind_host, bind_port


def main(argv: Sequence[str] | None = None) -> int:
    """Load persisted config, wire Hexagonal layers, and serve via Uvicorn."""
    args = build_argument_parser().parse_args(argv)
    repository = TomlConfigRepository(config_path=args.config)
    try:
        service = ConfigService(repository=repository)
        runtime_cfg = service.get_runtime_config()
        bind_host, bind_port = _resolve_bind_target(
            configured_host=runtime_cfg.server.host,
            configured_port=runtime_cfg.server.port,
            override_host=args.host,
            override_port=args.port,
        )
    except (ConfigPersistenceError, InvalidEndpointError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if args.check_config:
        whep_path = runtime_cfg.mediamtx.build_whep_path()
        stream_label = runtime_cfg.stream.resolution.get_label()
        print(
            f"Config OK ({args.config}): bind={bind_host}:{bind_port}, "
            f"whep={whep_path}, stream={stream_label}@{runtime_cfg.stream.fps_hz}Hz"
        )
        return 0

    app = create_backend_app(config_service=service)
    uvicorn.run(app, host=bind_host, port=bind_port)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
