# Rocket Telemetry Ground Station

> **Language / Idioma:** [ 🇬🇧 English ](README.md) | [ 🇪🇸 Español ](README.es.md)

A modular, asynchronous telemetry ground station designed for sounding and experimental rockets. The platform acquires high-frequency binary telemetry frames over a serial link (UART/USB/RF modem), validates packet integrity via CRC-16/CCITT-FALSE, decodes fields dynamically according to declarative YAML specifications, simultaneously persists data to SQLite and CSV, and broadcasts live metrics to a high-contrast web dashboard over WebSockets.

---

## Technical Documentation Suite

The complete technical documentation is available in both **English** and **Spanish** under [`docs/`](docs/) and [`docs/es/`](docs/es/):

| English | Español | Description / Descripción |
|---|---|---|
| **[System Architecture](docs/architecture.md)** | **[Arquitectura](docs/es/architecture.md)** | End-to-end data pipeline, `asyncio` concurrency, and decoupled frontend render engine. |
| **[Protocol Specification](docs/protocol.md)** | **[Protocolo Binario](docs/es/protocol.md)** | 65-byte definitive LoRa binary frame structure, memory map, and CRC-16 specification. |
| **[Frame Schema (YAML)](docs/frame-schema.md)** | **[Esquema de Trama](docs/es/frame-schema.md)** | Generic declarative schema specification: field properties, scaling, and parser rules. |
| **[Dashboard Specification](docs/frontend-dashboard.md)** | **[Tablero de Control](docs/es/frontend-dashboard.md)** | UI layout, visual hierarchy, instrument wireframes, and ergonomic design guidelines. |
| **[API & WebSocket](docs/api.md)** | **[API y WebSockets](docs/es/api.md)** | REST endpoints (`GET /`, `/gonogo`, `/api/status`), WebSocket schemas, and packet statistics. |
| **[Getting Started](docs/getting-started.md)** | **[Guía de Inicio](docs/es/getting-started.md)** | Developer setup, Linux serial permissions (`dialout`), and hardware-free simulation. |
| **[Contributing Guide](CONTRIBUTING.md)** | **[Guía de Contribución](CONTRIBUTING.es.md)** | Onboarding walkthrough, Git workflow, testing requirements, and PR review process. |
| **[Windows Packaging](docs/packaging-exe.md)** | **[Compilación Windows](docs/es/packaging-exe.md)** | Compiling standalone `.exe` with PyInstaller, `build_windows.bat`, or GitHub Actions. |
| **[Future Calculations](docs/calculos-futuros.md)** | **[Cálculos Futuros](docs/es/calculos-futuros.md)** | Kalman filter fusion, variometer ($V_z$), landing ellipse, and ISA-18.2 alarm specifications. |
| **[Pending Cleanups](docs/pending-deletions-list.md)** | **[Limpieza Pendiente](docs/es/pending-deletions-list.md)** | Inventory of relocated and clean-up candidate files for review. |

---

## Key Features

- **Asynchronous Serial Engine:** Non-blocking serial acquisition powered by `pyserial-asyncio` with automatic reconnection if the USB or RF link drops.
- **Declarative Protocol Schema:** Binary frame structure is governed entirely by [`config/frame.yaml`](config/frame.yaml). Modifying telemetry formats requires zero Python code changes.
- **Strict Integrity Verification:** Frame length enforcement, CRC-16/CCITT-FALSE verification, and fixed sync header (`0xAA`) noise immunity.
- **Quantitative Link Diagnostics:** Automatic packet sequence tracking, real-time packet loss calculation, rolling reception rate (Hz), and silence timeout detection.
- **Dual Persistent Storage:** Simultaneous recording to indexed SQLite database (`data/telemetry.db`) and immediately flushed flat-file CSV (`data/telemetry.csv`).
- **High-Contrast Mission Dashboard:** Zero-dependency Canvas instruments (aerospace moving altitude tape, time-series oscilloscopes), Leaflet GPS mapping, and ISA-18.2 operational alert badges engineered for sunlight readability.
- **Pre-Flight Go / No-Go Checklist:** Dedicated qualification console (`/gonogo`) verifying sensor baselines, stability hold counters, and weather limits.
- **Microcontroller Mission Simulator:** Ready-to-flash 290-second mission firmware in [`arduino/telemetry_simulator/`](arduino/telemetry_simulator/) for full end-to-end hardware-in-the-loop simulation.

---

## System Requirements

- **Python:** 3.10 or higher (Python 3.11+ recommended)
- **Supported OS:** Linux (Ubuntu, Debian, Raspberry Pi OS), Windows 10/11, macOS
- **Hardware Interface:** Any serial transceiver (USB CDC ACM, CP2102, FTDI, LoRa modem, SiK radio)

---

## Quick Start

### 1. Configure Linux Serial Permissions
On Linux, grant your user permission to read and write to the serial port:

```bash
sudo usermod -aG dialout $USER
newgrp dialout
```

### 2. Set Up Virtual Environment & Dependencies
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Linux / macOS
# .venv\Scripts\activate        # On Windows

# Install required dependencies
pip install -r requirements.txt
```

> **Note:** Always ensure the virtual environment is active (`source .venv/bin/activate`). Executing `main.py` directly under system Python will trigger an automatic dependency check reminding you to activate `.venv`.

### 3. Run Automated Tests
Verify that the environment and frame parser pass all tests:

```bash
python tests/test_telemetry_65b.py
# or using unittest discovery:
python -m unittest discover tests
```

### 4. Configure Hardware Link
Edit [`config/app.yaml`](config/app.yaml) with your serial port and desired network port:

```yaml
serial:
  port: "/dev/ttyACM0"   # Windows: "COM6", macOS: "/dev/cu.usbmodem1101"
  baudrate: 115200
  reconnect_delay: 3     # Retry delay in seconds

websocket:
  host: "0.0.0.0"        # Listen on all interfaces
  port: 8000

storage:
  database: "data/telemetry.db"
  csv: "data/telemetry.csv"
```

### 5. Run the Ground Station
```bash
python main.py
```

Open your browser to:
- **`http://localhost:8000`** $\to$ Real-time mission dashboard
- **`http://localhost:8000/gonogo`** $\to$ Pre-flight Go / No-Go qualification view

---

## API Summary

| Endpoint | Protocol | Description |
|---|---|---|
| `GET /` | HTTP | Serves the web dashboard (`frontend/index.html`) |
| `GET /gonogo` | HTTP | Serves the Go / No-Go pre-flight qualification view (`frontend/gonogo.html`) |
| `GET /api/status` | HTTP | System runtime health, serial link state, and packet loss metrics |
| `GET /api/telemetry` | HTTP | Latest received frame snapshot, decoded values, and raw hex |
| `WS /ws/telemetry` | WebSocket | Real-time bi-directional telemetry and event streaming |
| `WS /ws` | WebSocket | Stream alias for `/ws/telemetry` |

*For complete request/response schemas and examples, refer to [API Documentation](docs/api.md).*

---

## Project Structure

```text
.
├── main.py                  # Application core (FastAPI + serial_asyncio + parser + storage)
├── arduino/                 # Microcontroller firmware simulation (Arduino / ESP32 / STM32)
│   └── telemetry_simulator/ # 290-second flight profile simulator firmware
├── config/
│   ├── app.yaml             # Serial port, HTTP/WebSocket, and storage paths
│   └── frame.yaml           # Declarative 65-byte LoRa frame schema and CRC parameters
├── data/                    # Generated telemetry records (git-ignored)
│   ├── telemetry.db         # SQLite database
│   └── telemetry.csv        # Append-only CSV telemetry log
├── docs/                    # Comprehensive technical documentation
│   ├── api.md               # REST and WebSocket interface reference
│   ├── architecture.md      # End-to-end system architecture and data pipeline
│   ├── calculos-futuros.md  # Mathematical algorithms and future calculations
│   ├── frame-schema.md      # Declarative frame definition schema specification
│   ├── frontend-dashboard.md# Telemetry dashboard design and ergonomic specification
│   ├── getting-started.md   # Setup, operations, and developer testing manual
│   ├── packaging-exe.md     # PyInstaller Windows standalone compilation guide
│   └── protocol.md          # 65-byte LoRa binary frame specification and CRC-16 reference
├── frontend/
│   ├── index.html           # Single-page high-contrast mission dashboard
│   ├── gonogo.html          # Pre-launch Go / No-Go qualification view
│   ├── css/style.css        # Supplemental styling
│   └── assets/              # Project graphics and logos
├── tests/
│   ├── __init__.py          # Test suite package marker
│   └── test_telemetry_65b.py# Automated verification (parser, CRC, sliding window, DB)
├── build_windows.bat        # 1-click Windows executable builder
├── ground_station.spec      # PyInstaller frozen bundle specification
├── CONTRIBUTING.md          # Team contribution, onboarding, and PR guidelines
├── README.md                # Project entry point and documentation index
└── requirements.txt         # Python runtime dependencies
```

---

## Contributing & Onboarding

We welcome contributions from everyone on the team! Before opening a pull request, please review [CONTRIBUTING.md](CONTRIBUTING.md) for onboarding instructions, code conventions, testing requirements, and Git workflow.

---

## License & Attribution

Developed for sounding rocket avionics monitoring by the Ground Station engineering team.
