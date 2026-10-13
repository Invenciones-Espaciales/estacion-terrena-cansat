# Rocket Telemetry Ground Station

A modular, asynchronous telemetry ground station designed for sounding and experimental rockets. The platform acquires high-frequency binary telemetry frames over a serial link (UART/USB/RF modem), validates packet integrity via CRC-16/CCITT-FALSE, decodes fields dynamically according to declarative YAML specifications, simultaneously persists data to SQLite and CSV, and broadcasts live metrics to a high-contrast web dashboard over WebSockets.

---

## Technical Documentation Suite

The complete technical documentation is organized under the [`docs/`](docs/) directory:

| Document | Description |
|---|---|
| **[System Architecture](docs/architecture.md)** | End-to-end data flow pipeline, `asyncio` concurrency model, task lifecycle, and decoupled multi-tiered frontend render engine. |
| **[Protocol Specification](docs/protocol.md)** | 30-byte binary frame structure, bit-level memory map, data types, physical scale factors, flight states, and CRC-16/CCITT-FALSE specification. |
| **[API & WebSocket Specification](docs/api.md)** | REST endpoints (`GET /`, `GET /api/status`, `GET /api/telemetry`), WebSocket protocol schemas, packet statistics, and reconnection state machines. |
| **[Getting Started & Operations](docs/getting-started.md)** | Detailed developer setup, Linux serial permissions (`dialout`), configuration guide, hardware-free testing (`socat`), and troubleshooting. |
| **[Future Calculations Reference](docs/calculos-futuros.md)** | Extended avionics algorithms: Kalman filter fusion, variometer ($V_z$), landing ellipse, antenna tracking, and ISA-18.2 alarm specifications. |
| **[Frame Schema Specification](config.md)** | Generic declarative schema specification: field properties, scaling, data types, and parser operation. |
| **[Dashboard Visual Specification](front.md)** | Telemetry dashboard UI layout, visual hierarchy, instrument wireframes, and ergonomic design guidelines. |
| **[Windows Executable Packaging](docs/packaging-exe.md)** | Instructions for compiling standalone Windows `.exe` using PyInstaller, `build_windows.bat`, or automated GitHub Actions. |

---

## Key Features

- **Asynchronous Serial Engine:** Non-blocking serial acquisition powered by `pyserial-asyncio` with automatic reconnection if the USB or RF link drops.
- **Declarative Protocol Schema:** Binary frame structure is governed entirely by [`config/frame.yaml`](config/frame.yaml). Modifying telemetry formats requires zero code changes.
- **Strict Integrity Verification:** Frame length enforcement, CRC-16/CCITT-FALSE verification, and header sanity checks.
- **Quantitative Link Diagnostics:** Automatic packet sequence tracking, real-time packet loss calculation, rolling reception rate (Hz), and silence timeout detection.
- **Dual Persistent Storage:** Simultaneous recording to indexed SQLite database (`data/telemetry.db`) and immediately flushed flat-file CSV (`data/telemetry.csv`).
- **High-Contrast Mission Dashboard:** Zero-dependency Canvas instruments (aerospace moving altitude tape, time-series oscilloscopes), Leaflet GPS mapping, and ISA-18.2 operational alert badges engineered for sunlight readability.

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


### 3. Configure Hardware Link
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

### 4. Run the Ground Station
```bash
python main.py
```

Open your browser to **`http://localhost:8000`** to access the live dashboard.

---

## API Summary

| Endpoint | Protocol | Description |
|---|---|---|
| `GET /` | HTTP | Serves the web dashboard (`frontend/index.html`) |
| `GET /api/status` | HTTP | System runtime health, serial link state, and packet loss metrics |
| `GET /api/telemetry` | HTTP | Latest received frame snapshot, decoded values, and raw hex |
| `WS /ws/telemetry` | WebSocket | Real-time bi-directional telemetry and event streaming |
| `WS /ws` | WebSocket | Stream alias for `/ws/telemetry` |

*For complete request/response schemas and examples, refer to [API Documentation](docs/api.md).*

---

## Project Structure

```text
.
├── main.py              # Application core (FastAPI + serial_asyncio + parser + storage)
├── arduino/             # Microcontroller firmware simulation (Arduino / ESP32 / STM32)
├── config/
│   ├── app.yaml         # Serial port, HTTP/WebSocket, and storage paths
│   └── frame.yaml       # Declarative binary frame schema and CRC configuration
├── config.md            # Declarative frame definition schema specification
├── data/                # Generated telemetry records (git-ignored)
│   ├── telemetry.db     # SQLite database
│   └── telemetry.csv    # Append-only CSV telemetry log
├── docs/                # Comprehensive technical documentation
│   ├── api.md           # REST and WebSocket interface reference
│   ├── architecture.md  # End-to-end system architecture and data pipeline
│   ├── calculos-futuros.md # Mathematical algorithms and future calculations
│   ├── getting-started.md # Setup, operations, and developer testing manual
│   └── protocol.md      # Binary frame specification and CRC-16 reference
├── front.md             # Telemetry dashboard design and ergonomic specification
├── frontend/
│   ├── index.html       # Single-page high-contrast mission dashboard
│   ├── css/style.css    # Supplemental styling
│   └── assets/          # Project graphics and logos
├── README.md            # Project entry point and documentation index
└── requirements.txt     # Python runtime dependencies
```

---

## License & Attribution

Developed for sounding rocket avionics monitoring by the Ground Station engineering team.
