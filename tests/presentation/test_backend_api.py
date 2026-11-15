"""Tests for FastAPI presentation routes, static UI serving, and backend CLI."""

from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from real_time_cam.application.config_service import ConfigService
from real_time_cam.domain.entities import BackendRuntimeConfig
from real_time_cam.domain.errors import ConfigPersistenceError, InvalidStreamConfigError
from real_time_cam.infrastructure.persistence.toml_config_repository import (
    TomlConfigRepository,
)
from real_time_cam.presentation.backend import cli as backend_cli
from real_time_cam.presentation.backend.app_factory import create_backend_app

UPDATED_FPS_HZ: int = 25
UPDATED_BITRATE_KBPS: int = 3200
CLI_CONFIG_ERROR_EXIT_CODE: int = 2
CUSTOM_PORT: int = 18081


class FailingSaveRepository:
    """Repository stub that loads cleanly but fails on save to test HTTP 500."""

    def load_or_create_default(self) -> BackendRuntimeConfig:
        return BackendRuntimeConfig()

    def save(self, config: BackendRuntimeConfig) -> None:
        msg = f"Disk write failed for {config.stream.fps_hz}"
        raise ConfigPersistenceError(msg)


def test_backend_serves_web_ui_health_and_persists_stream_config(
    tmp_path: Path,
) -> None:
    """Verify static page, bootstrap endpoint, PUT persistence, and reset."""
    toml_path = tmp_path / "backend.toml"
    service = ConfigService(repository=TomlConfigRepository(toml_path))
    client = TestClient(create_backend_app(config_service=service))

    html_resp = client.get("/")
    assert html_resp.status_code == HTTPStatus.OK
    assert 'id="live-video"' in html_resp.text

    js_resp = client.get("/js/api-client.js")
    assert js_resp.status_code == HTTPStatus.OK

    assert client.get("/docs").status_code == HTTPStatus.NOT_FOUND
    assert client.get("/api/openapi.json").status_code == HTTPStatus.OK

    health = client.get("/api/v1/health")
    assert health.status_code == HTTPStatus.OK
    assert health.json()["status"] == "ok"

    bootstrap = client.get("/api/v1/config").json()
    assert bootstrap["mediamtx"]["whep_path"] == "/cam/whep"
    assert bootstrap["stream"]["resolution"] == "960x600"

    put_resp = client.put(
        "/api/v1/config/stream",
        json={
            "resolution": "1920x1200",
            "fps_hz": UPDATED_FPS_HZ,
            "bitrate_kbps": UPDATED_BITRATE_KBPS,
            "encoder_kind": "software_x264",
        },
    )
    assert put_resp.status_code == HTTPStatus.OK
    assert put_resp.json()["fps_hz"] == UPDATED_FPS_HZ

    reloaded_service = ConfigService(repository=TomlConfigRepository(toml_path))
    assert reloaded_service.get_stream_config().fps_hz == UPDATED_FPS_HZ
    assert client.get("/api/v1/config/stream").json()["fps_hz"] == UPDATED_FPS_HZ

    reset_resp = client.post("/api/v1/config/stream/reset")
    assert reset_resp.status_code == HTTPStatus.OK
    assert reset_resp.json()["resolution"] == "960x600"


@pytest.mark.parametrize(
    "bad_payload",
    [
        {
            "resolution": "1280x720",
            "fps_hz": 30,
            "bitrate_kbps": 2000,
            "encoder_kind": "software_x264",
        },
        {
            "resolution": "1920x1200",
            "fps_hz": 30,
            "bitrate_kbps": 2000,
            "encoder_kind": "hardware_v4l2",
        },
        {
            "resolution": "960x600",
            "fps_hz": 30,
            "bitrate_kbps": 2000,
            "encoder_kind": "software_x264",
            "unexpected": 1,
        },
    ],
)
def test_backend_rejects_invalid_stream_payloads_with_422(
    tmp_path: Path,
    bad_payload: dict[str, object],
) -> None:
    """Verify Pydantic V2 boundary rejects bad resolutions, V4L2 limits, and typos."""
    service = ConfigService(repository=TomlConfigRepository(tmp_path / "backend.toml"))
    client = TestClient(create_backend_app(config_service=service))

    resp = client.put("/api/v1/config/stream", json=bad_payload)
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_backend_translates_persistence_and_domain_errors() -> None:
    """Verify persistence errors return HTTP 500 and bad web_root raises."""
    failing_service = ConfigService(repository=FailingSaveRepository())
    client = TestClient(create_backend_app(config_service=failing_service))

    put_resp = client.put(
        "/api/v1/config/stream",
        json={
            "resolution": "960x600",
            "fps_hz": 20,
            "bitrate_kbps": 1500,
            "encoder_kind": "software_x264",
        },
    )
    assert put_resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    reset_resp = client.post("/api/v1/config/stream/reset")
    assert reset_resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    with pytest.raises(FileNotFoundError):
        create_backend_app(
            config_service=failing_service,
            web_root=Path("/nonexistent/xerox/web"),
        )


def test_backend_route_translates_domain_error_from_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify InvalidStreamConfigError raised inside service maps to HTTP 422."""
    service = ConfigService(repository=TomlConfigRepository(tmp_path / "backend.toml"))

    def _raise_domain(_stream: object) -> None:
        msg = "Forced domain rejection"
        raise InvalidStreamConfigError(msg)

    monkeypatch.setattr(service, "apply_stream_config", _raise_domain)
    client = TestClient(create_backend_app(config_service=service))

    resp = client.put(
        "/api/v1/config/stream",
        json={
            "resolution": "960x600",
            "fps_hz": 30,
            "bitrate_kbps": 2000,
            "encoder_kind": "software_x264",
        },
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_backend_cli_check_config_and_uvicorn_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify xerox-cam-backend CLI --check-config, overrides, and error codes."""
    cfg_path = tmp_path / "backend.toml"

    exit_ok = backend_cli.main(["--config", str(cfg_path), "--check-config"])
    assert exit_ok == 0
    assert cfg_path.is_file()

    bad_port_code = backend_cli.main(
        ["--config", str(cfg_path), "--port", "0", "--check-config"]
    )
    assert bad_port_code == CLI_CONFIG_ERROR_EXIT_CODE

    bad_host_code = backend_cli.main(
        ["--config", str(cfg_path), "--host", "bad host", "--check-config"]
    )
    assert bad_host_code == CLI_CONFIG_ERROR_EXIT_CODE

    captured: dict[str, object] = {}

    def _fake_uvicorn_run(app: object, host: str, port: int) -> None:
        captured["app"] = app
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setattr("uvicorn.run", _fake_uvicorn_run)
    run_code = backend_cli.main(
        [
            "--config",
            str(cfg_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(CUSTOM_PORT),
        ]
    )
    assert run_code == 0
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == CUSTOM_PORT
