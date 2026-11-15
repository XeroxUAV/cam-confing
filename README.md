# XeroxUAV Live Camera Configurator — Base Setup

A small, self-contained tool that shows the quadcopter's **live camera feed in a web browser** with sub-second latency, over a plain local network (LAN cable or phone hotspot) — **no internet required**.

Teammates do not install anything: they open one URL and watch the video.

> **فارسی:** برای راهنمای فارسی [`README.fa.md`](README.fa.md) را بخوان.
>
> **Golden Propeller Rule:** propellers must be physically **removed** during every software setup, bench test, and debugging session described here.

---

## Contents

| I want to… | Go to |
| :--- | :--- |
| Start the system right now (everything already installed) | [Quick Start](#1-quick-start) |
| Set up a fresh laptop or Raspberry Pi | [One-time setup](#3-one-time-setup) |
| Change resolution / fps / bitrate | [Configuration](#4-configuration) |
| Fix something that is broken | [Troubleshooting](#7-troubleshooting) |

---

## 1. Quick Start

Everything below assumes the one-time setup in [section 3](#3-one-time-setup) is already done on the machines
(`uv`, `MediaMTX`, project files, GStreamer, firewall rules).

Open **three terminals**: two PowerShell windows on the Windows laptop and one SSH session on the Raspberry Pi.

### Step 1 — Start the media server (laptop, PowerShell window #1)

```powershell
cd C:\Users\<username>\Documents\configurator
.\bin\mediamtx.exe .\configs\mediamtx.yml
```

Expected output (5 lines):

```text
INF MediaMTX v1.21.3, windows, amd64
INF configuration loaded from ...\configs\mediamtx.yml
INF [RTSP] started with listeners on :8554 (TCP/RTSP), :8000 (UDP/RTP), :8001 (UDP/RTCP)
INF [HLS] started with listener on :8888 (TCP/HTTP)
INF [WebRTC] started with listeners on :8889 (TCP/HTTP), :8189 (UDP/ICE)
```

Keep this window open.

### Step 2 — Start the backend + web page (laptop, PowerShell window #2)

```powershell
cd C:\Users\<username>\Documents\configurator
uv run xerox-cam-backend
```

Expected output:

```text
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
```

Keep this window open too — closing it takes the web page down for everyone.

### Step 3 — Start the camera stream (Raspberry Pi, SSH)

Find the laptop's current IP first (`ipconfig` on the laptop), then:

```bash
cd ~/projects/real_time_cam
uv run xerox-cam-push --mediamtx-host <LAPTOP_IP> --resolution 960x600 --fps-hz 30 --bitrate-kbps 2000 --encoder software_x264
```

Expected output: the printed `gst-launch-1.0 ...` command followed by `Setting pipeline to PLAYING ...`, and in the
MediaMTX window a new line:

```text
INF [path cam] [RTSP source] is publishing to path 'cam', 1 track (H264)
```

### Step 4 — Open the URL

| Where | URL |
| :--- | :--- |
| On the ground-station laptop | `http://127.0.0.1:8080/` |
| On any other team device on the same network | `http://<LAPTOP_IP>:8080/` |
| Direct WebRTC test page (our UI not involved) | `http://<LAPTOP_IP>:8889/cam/` |
| HLS fallback (higher latency) | `http://<LAPTOP_IP>:8888/cam/` |

The page connects automatically. A green **LIVE** badge over the video means everything works.

> The UI is Persian/RTL with English technical labels. The status badge reads
> «پخش زنده» = *LIVE*, «در حال اتصال...» = *Connecting…*, «آماده اتصال» = *Ready*, «خطای ارتباط» = *Connection error*.

### Stop / restart order

Stop with `Ctrl+C` in this order: Pi push → backend → MediaMTX. To restart after a network unplug, repeat steps 1–4.

---

## 2. Requirements

| Item | Requirement |
| :--- | :--- |
| Ground station | Windows 10/11 laptop |
| Onboard computer | Raspberry Pi 4 (`xerox@XeroxUAV`, Debian 13 `aarch64`, Python 3.13) |
| Camera | Arducam B0495 on a **blue USB 3.0 port** (a black USB 2.0 port drops the camera to 10 fps) |
| Network | LAN cable between laptop and Pi, or a phone hotspot; both devices on the same network |
| Laptop software | `uv`, this repo, `bin\mediamtx.exe`, firewall rules (once) |
| Pi software | GStreamer 1.26+ with `ugly`, `bad`, `rtsp` plugins, `v4l-utils`, this repo |
| Viewers | Any modern Chrome, Edge, or Firefox — no install needed |

---

## 3. One-time setup

### 3.1 Windows laptop

```powershell
# 1) Install uv (close and reopen PowerShell afterwards)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv --version
```

```powershell
# 2) Install project dependencies (internet needed only here)
cd C:\Users\<username>\Documents\configurator
uv sync --locked --dev
```

```powershell
# 3) Download the media server (MediaMTX v1.21.3)
New-Item -ItemType Directory -Force -Path .\bin | Out-Null
Invoke-WebRequest -Uri "https://github.com/bluenviron/mediamtx/releases/download/v1.21.3/mediamtx_v1.21.3_windows_amd64.zip" -OutFile .\bin\mediamtx.zip
Expand-Archive -Force -Path .\bin\mediamtx.zip -DestinationPath .\bin
Unblock-File -Path .\bin\mediamtx.exe
.\bin\mediamtx.exe --version      # -> v1.21.3
```

```powershell
# 4) Open the firewall ports once, in an Administrator PowerShell
New-NetFirewallRule -DisplayName "XeroxUAV Camera TCP" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8554,8888,8889,8080 -Profile Any
New-NetFirewallRule -DisplayName "XeroxUAV Camera UDP" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 8000,8001,8189 -Profile Any
```

If Windows shows *“Windows protected your PC”*, click **More info → Run anyway**.
Port `8080` is the web page; `-Profile Any` is required because Windows often marks hotspots as *Public*.

### 3.2 Raspberry Pi

```bash
# 1) Verify the camera (expect 'YUYV' with 960x600 @ 80 fps and 1920x1200 @ 50 fps)
v4l2-ctl --device=/dev/video1 --list-formats-ext
```

If you only see `960x600 @ 10.000 fps`, the camera is on a USB 2.0 port — move it to a **blue USB 3.0** port.

```bash
# 2) Install system packages (once)
sudo apt update && sudo apt install -y v4l-utils gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-rtsp
```

```bash
# 3) Copy this repo to the Pi (from the laptop)
#    scp "$HOME\Downloads\real_time_cam.zip" xerox@XeroxUAV:~/
mkdir -p ~/projects/real_time_cam
tar -xzf ~/real_time_cam.zip -C ~/projects/real_time_cam --strip-components=1
cd ~/projects/real_time_cam
uv sync --dev
```

---

## 4. Configuration

Stream settings live in `configs\backend.toml` on the laptop (created automatically on first run; git-ignored, so a
local IP never ends up in git). Read or change them while the backend is running:

```powershell
# Read current settings
Invoke-RestMethod -Uri http://127.0.0.1:8080/api/v1/config/stream

# Apply new settings
Invoke-RestMethod -Method Put -Uri http://127.0.0.1:8080/api/v1/config/stream `
  -ContentType "application/json" `
  -Body '{"resolution":"1920x1200","fps_hz":25,"bitrate_kbps":3000,"encoder_kind":"software_x264"}'

# Restore defaults (960x600 @ 30 Hz @ 2000 kbps)
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/api/v1/config/stream/reset
```

> **Current behaviour:** saving settings only *persists* them. To make them take effect on the live video, stop
> (`Ctrl+C`) and re-run the `xerox-cam-push` command on the Pi with the same new values.

### Valid ranges (enforced by the backend)

| Setting | Allowed values |
| :--- | :--- |
| `resolution` | `960x600` or `1920x1200` |
| `fps_hz` | `5` – `60` |
| `bitrate_kbps` | `300` – `12000` |
| `encoder_kind` | `software_x264` (always) or `hardware_v4l2` (heights up to `1080` only) |

Invalid combinations are rejected with HTTP `422` and the file is left untouched.

### Ports

| Port | Protocol | Service | Who connects |
| :--- | :--- | :--- | :--- |
| `8554` | TCP | MediaMTX RTSP ingest | Raspberry Pi |
| `8000` / `8001` | UDP | MediaMTX RTP / RTCP | Raspberry Pi |
| `8889` | TCP | MediaMTX WebRTC (WHEP) | Browsers |
| `8189` | UDP | MediaMTX ICE media | Browsers |
| `8888` | TCP | MediaMTX HLS fallback | Browsers |
| `8080` | TCP | Backend (web UI + API) | Browsers |

None of these collide with UDP port `5000`, which is occupied on the team laptop.

---

## 5. Demo mode (no camera, no Raspberry Pi)

To show the pipeline on the Windows laptop alone (requires GStreamer on Windows):

```powershell
gst-launch-1.0 -e videotestsrc is-live=true pattern=ball ! video/x-raw,width=960,height=600,framerate=30/1,format=I420 ! x264enc tune=zerolatency speed-preset=ultrafast bitrate=2000 key-int-max=30 ! video/x-h264,profile=baseline ! h264parse ! rtspclientsink location=rtsp://127.0.0.1:8554/cam protocols=tcp latency=0
```

Expected: `is publishing to path 'cam', 1 track (H264)` in the MediaMTX window, and a smoothly moving white ball in
the browser — the easiest way to eyeball latency without hardware.

---

## 6. Acceptance checklist

- [ ] Propellers removed (Golden Propeller Rule).
- [ ] MediaMTX window shows the 5 `INF` startup lines **and** `is publishing to path 'cam', 1 track (H264)`.
- [ ] `uv run xerox-cam-backend` is running and prints `Uvicorn running on http://0.0.0.0:8080`.
- [ ] `http://127.0.0.1:8080/` on the laptop shows the live video with the LIVE badge.
- [ ] `http://<LAPTOP_IP>:8080/` on **another** device on the same network shows the same video.
- [ ] Measured glass-to-glass latency is under one second (hold a phone stopwatch in front of the camera and compare).

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
| :--- | :--- | :--- |
| `This site can't be reached` | Backend is down or wrong IP | Run `uv run xerox-cam-backend`; re-check the IP with `ipconfig` |
| Page opens but shows *Connection error* | MediaMTX down, or nothing publishing | Check window #1 for the 5 `INF` lines and `is publishing to path 'cam'` |
| Stuck on *Connecting…* | Firewall blocks `8889` / `8189` | Re-run the firewall commands in [3.1](#31-windows-laptop) as Administrator |
| Pi: `Could not open device` | Camera on a USB 2.0 port or wrong `/dev/videoX` | Move to a blue USB 3.0 port; check `v4l2-ctl --list-devices`, pass `--device /dev/videoX` |
| No `is publishing` message | Wrong `--mediamtx-host` IP or port `8554` blocked | Re-read `ipconfig`; verify the firewall rule |
| `Only one usage of each socket address is normally permitted` | Another `mediamtx.exe` is already open | `Stop-Process -Name mediamtx` |
| Backend: port `8080` already in use | Another server holds it | Close it, or run with `--port 8081` |
| HTTP `422` when saving settings | Invalid combination (e.g. `1920x1200` + `hardware_v4l2`) | Use the ranges in [section 4](#4-configuration) |
| Video works on the laptop but not on phones | Phone on a different network, or missing `http://` | Join the same network and type the full `http://<LAPTOP_IP>:8080/` |

---

## 8. FAQ

**Does this need internet?** No. Everything runs on the local network with no CDN or external server. Internet is
only needed for the one-time install of `uv` and `MediaMTX`.

**Why is the IP never stored in a file?** Because it changes with every network, and a stale IP breaks a test day.
Everything is read from `configs\backend.toml` or a CLI argument (`--mediamtx-host`).

**How many people can watch at once?** As many as the network carries; MediaMTX fans the stream out to all viewers.
Phone hotspots may saturate with several simultaneous viewers — prefer a LAN cable.

**Why does the page connect by itself?** On load, the page fetches `/api/v1/config` from the backend and builds the
WHEP URL from it, so there is nothing to fill in.

**What if we change the ground-station laptop?** Nothing in the code changes; repeat [section 3.1](#31-windows-laptop)
and hand out the new IP.

---

## 9. For developers

```bash
uv sync --locked --dev
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest          # 76 passed, 97.83% branch coverage
```

Layout (hexagonal architecture — dependencies point inwards, `domain/` imports no framework):

```text
src/real_time_cam/
├── domain/          pure rules and frozen entities (no frameworks)
├── application/     use cases (e.g. load/persist stream configuration)
├── infrastructure/  TOML persistence, GStreamer encoders, system metrics
└── presentation/    FastAPI backend, web UI, Raspberry Pi CLI
```

| Entry point | Purpose |
| :--- | :--- |
| `xerox-cam-backend` | FastAPI server: serves the web UI and the `/api/v1` REST API on port `8080` |
| `xerox-cam-push` | Captures the camera, encodes H.264, and pushes RTSP to MediaMTX |
| `xerox-cam-benchmark` | Measures fps/CPU/temperature for both encoders on the Pi |

REST API: `GET /api/v1/health`, `GET /api/v1/config`, `GET|PUT /api/v1/config/stream`,
`POST /api/v1/config/stream/reset`.

A detailed, Persian, step-by-step explanation of every concept lives in [`docs/`](docs/00-overview.md).
