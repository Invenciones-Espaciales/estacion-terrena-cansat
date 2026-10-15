# Getting Started & Operations Guide

> **Language / Idioma:** [ 🇬🇧 English ](getting-started.md) | [ 🇪🇸 Español ](es/getting-started.md)

This guide provides complete instructions for configuring, deploying, operating, and verifying the **Rocket Telemetry Ground Station** (`estacion-terrena-pc`).

---

## 1. Prerequisites

### 1.1 Software Requirements
- **Python:** 3.10 or higher (Python 3.11+ recommended).
- **Operating System:**
  - Linux (Debian, Ubuntu, Raspberry Pi OS, Arch, Fedora).
  - Windows 10/11 (x86_64).
  - macOS (Apple Silicon / Intel).
- **Web Browser:** Any modern evergreen browser (Chrome, Firefox, Edge, Safari) with HTML5 Canvas and WebSocket support.

### 1.2 Hardware Requirements
- A ground station transceiver or USB-to-UART bridge connected to the PC:
  - USB CDC ACM Virtual COM Port (e.g., STM32, Raspberry Pi Pico, Teensy).
  - USB UART Bridges (FTDI FT232, CP2102, CH340).
  - RF Telemetry Modems (LoRa SX1262/SX1276 serial modules, SiK 433/915 MHz radios).

---

## 2. Operating System & Serial Port Permissions

### 2.1 Linux Serial Permissions (`dialout` / `uucp`)
By default, Linux limits serial device access (`/dev/ttyACM*` or `/dev/ttyUSB*`) to `root` and the `dialout` (or `uucp`) group.

1. Add your user account to the `dialout` group:
   ```bash
   sudo usermod -aG dialout $USER
   ```
   *(On Arch Linux / openSUSE, use group `uucp`: `sudo usermod -aG uucp $USER`)*

2. Apply group changes:
   Log out and log back in, or activate the group in your current shell:
   ```bash
   newgrp dialout
   ```

3. Identify the attached serial device:
   ```bash
   ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
   ```
   Or inspect kernel boot logs:
   ```bash
   dmesg | grep -E "tty(ACM|USB)"
   ```

### 2.2 Windows Serial Ports
- Identify your port in **Device Manager** under **Ports (COM & LPT)** (e.g. `COM3`, `COM6`).
- Set the `port` property in `config/app.yaml` to `"COMx"` (e.g. `"COM6"`).
- `main.py` automatically sets `asyncio.WindowsSelectorEventLoopPolicy()` on Windows to ensure `pyserial-asyncio` operates stably.

---

## 3. Environment Setup & Installation

### 3.1 Create Virtual Environment
Clone the repository (or navigate to the workspace directory) and initialize an isolated virtual environment:

```bash
# Navigate to project root
cd estacion-terrena-pc

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment (REQUIRED before running the ground station)
# On Linux / macOS:
source .venv/bin/activate

# On Windows (PowerShell):
# .venv\Scripts\Activate.ps1

# On Windows (CMD):
# .venv\Scripts\activate.bat
```

> **Important:** Always activate the virtual environment (`source .venv/bin/activate`) before running `python main.py`. If executed with system Python, a `ModuleNotFoundError: No module named 'serial_asyncio'` or `'fastapi'` will occur.


### 3.2 Install Dependencies
Install all required packages from `requirements.txt`:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### Included Packages:
- `fastapi`: High-performance asynchronous web framework.
- `uvicorn[standard]`: ASGI production-grade HTTP/WebSocket server.
- `pyyaml`: YAML parser for application and frame schemas.
- `pyserial`: Core serial communications library.
- `pyserial-asyncio`: Asynchronous protocol-transport engine for `asyncio`.

---

## 4. Configuration Reference (`config/app.yaml`)

Edit [`config/app.yaml`](../config/app.yaml) to match your local serial port and network environment:

```yaml
serial:
  port: "/dev/ttyACM0"      # Serial port device (Windows: "COM6", macOS: "/dev/cu.usbmodem1101")
  baudrate: 115200          # UART baud rate (e.g., 9600, 57600, 115200)
  reconnect_delay: 3        # Seconds to wait between serial reconnect attempts

websocket:
  host: "0.0.0.0"           # "0.0.0.0" allows access from local LAN; "127.0.0.1" for local only
  port: 8000                # HTTP and WebSocket port

storage:
  database: "data/telemetry.db"  # SQLite database destination path
  csv: "data/telemetry.csv"      # Flat CSV telemetry destination path
```

### Path Resolution Rules
If relative paths are specified under `storage`:
- Single-component paths (e.g., `telemetry.db`) default to the `data/` directory (`data/telemetry.db`).
- Subdirectory paths (e.g., `data/telemetry.db`) resolve relative to the project root.
- The application automatically ensures destination parent folders exist before writing.

---

## 5. Execution & Operations

### 5.1 Starting the Ground Station
Activate your virtual environment and start the backend service:

```bash
python main.py
```

### 5.2 Startup Sequence Logs
Upon startup, the server emits structured log messages:
```text
YYYY-MM-DD HH:MM:SS,MS | INFO | Inicializando Ground Station...
YYYY-MM-DD HH:MM:SS,MS | INFO | Frame configurado | payload=28 bytes | frame=30 bytes
YYYY-MM-DD HH:MM:SS,MS | INFO | Base de datos: /home/.../data/telemetry.db
YYYY-MM-DD HH:MM:SS,MS | INFO | CSV: /home/.../data/telemetry.csv
YYYY-MM-DD HH:MM:SS,MS | INFO | Conectando UART /dev/ttyACM0 @ 115200
YYYY-MM-DD HH:MM:SS,MS | INFO | Puerto UART abierto correctamente
YYYY-MM-DD HH:MM:SS,MS | INFO | UART conectada
YYYY-MM-DD HH:MM:SS,MS | INFO | Ground Station iniciada
YYYY-MM-DD HH:MM:SS,MS | INFO | Started server process [PID]
YYYY-MM-DD HH:MM:SS,MS | INFO | Uvicorn running on http://0.0.0.0:8000
```

### 5.3 Accessing the Dashboard
Open your web browser and navigate to:
```text
http://localhost:8000
```

If connecting from another laptop or tablet on the same local network:
```text
http://<GROUND_STATION_IP>:8000
```

---

## 6. End-to-End Verification & Testing

### 6.1 Hardware-Free Simulation via Virtual Serial Port (Linux)
You can test the entire pipeline without physical avionics hardware using `socat` to create a virtual null-modem serial pair.

1. Install `socat` (if not already installed):
   ```bash
   sudo apt install -y socat
   ```

2. In a separate terminal, spawn connected virtual pseudo-terminals:
   ```bash
   socat -d -d pty,raw,echo=0 pty,raw,echo=0
   ```
   `socat` will output two connected pseudo-terminals, for example:
   ```text
   2026/10/13 18:00:00 socat[12345] N PTY is /dev/pts/2
   2026/10/13 18:00:00 socat[12345] N PTY is /dev/pts/3
   ```

2. Point `config/app.yaml` to the first port:
   ```yaml
   serial:
     port: "/dev/pts/2"
     baudrate: 115200
     reconnect_delay: 3
   ```

3. Send simulated 65-byte frames into `/dev/pts/3` using a lightweight Python generator:
   ```python
   # mock_feeder.py
   import struct
   import time

   def crc16_ccitt(data: bytes) -> int:
       crc = 0xFFFF
       for b in data:
           crc ^= (b << 8)
           for _ in range(8):
               if crc & 0x8000:
                   crc = ((crc << 1) ^ 0x1021) & 0xFFFF
               else:
                   crc = (crc << 1) & 0xFFFF
       return crc

   with open("/dev/pts/3", "wb", buffering=0) as pty:
       seq = 0
       t_start = time.time()
       while True:
           t_ms = int((time.time() - t_start) * 1000) & 0xFFFFFFFF
           # 63 bytes payload: sync(AA), seq, timestamp, status, pressure, alt,
           # ax, ay, az, gx, gy, gz, temp, lat, lon, alt_gps, sats, spd, pin1, pin2
           payload = struct.pack(
               '<B H I B f f f f f f f f f f f f B f B B',
               0xAA,           # sync
               seq,            # frame_number
               t_ms,           # timestamp (ms)
               1,              # status (1 = POWERED)
               1013.25,        # pressure (hPa)
               120.5,          # altura_actual (m)
               0.05, -0.02, 1.02, # accel_x, y, z (g)
               0.5, -0.3, 12.4,   # gyro_x, y, z (deg/s)
               28.5,           # temp_imu (°C)
               -34.603722, -58.381592, # latitude, longitude
               125.0,          # altitud_gps (m)
               12,             # satellites
               15.4,           # ground_speed (m/s)
               0, 0            # pin_frenado, pin_principal
           )
           crc = crc16_ccitt(payload)
           packet = payload + crc.to_bytes(2, byteorder='little')
           pty.write(packet)
           seq = (seq + 1) & 0xFFFF
           time.sleep(0.1)     # 10 Hz
   ```

4. Run `python mock_feeder.py` and observe the live instruments updating on the browser dashboard!

### 6.2 Running the Firmware Simulator (Arduino / ESP32)
For end-to-end hardware-in-the-loop simulation, flash the complete 290-second mission profile simulator provided in [`arduino/telemetry_simulator/`](../arduino/telemetry_simulator/):
- Emulates pre-launch pad noise, powered ascent (9.8g), burnout coast, apogee, drogue chute deployment, main parachute reefing, and touchdown.
- Tests in-flight ISA-18.2 alerts: excessive lateral G-force, packet loss bursts, and CRC corruptions.
- Refer to [`arduino/telemetry_simulator/README.md`](../arduino/telemetry_simulator/README.md) for 1-click flashing instructions.

### 6.3 Running Automated Test Suite
Execute the comprehensive automated test suite to verify configuration loading, field decoding, CRC rejection, sliding window resynchronization, and dual storage persistence:
```bash
python tests/test_telemetry_65b.py
# or using unittest discovery
python -m unittest discover tests
```

---

### 6.4 Verifying the REST API
Check the health status endpoint:
```bash
curl -s http://localhost:8000/api/status | jq
```

Expected output:
```json
{
  "connected": true,
  "frames_received": 52,
  "last_timestamp": 1718300050.2,
  "serial_port": "/dev/ttyACM0",
  "baudrate": 115200,
  "statistics": {
    "received": 52,
    "lost": 0,
    "invalid": 0,
    "loss_percent": 0.0
  }
}
```

Check the latest telemetry frame:
```bash
curl -s http://localhost:8000/api/telemetry | jq
```

---

### 6.5 Verifying Persistent Storage
Confirm that telemetry is being recorded to SQLite and CSV:

```bash
# Check SQLite row count
sqlite3 data/telemetry.db "SELECT COUNT(*), id, timestamp, payload FROM telemetry ORDER BY id DESC LIMIT 1;"

# Check CSV tail
tail -n 5 data/telemetry.csv
```

---

### 6.6 Physical RF Hardware Deployment & Over-the-Air Verification (LoRa / SiK Radios)

When transitioning from virtual loopback simulation to physical sounding rocket flight operations, configure and verify the wireless radio link:

#### 1. Supported Physical Transceivers
- **SiK Telemetry Radios (433 MHz / 915 MHz):** Silicon Labs Si1000/HM-TRP based modems (e.g. Holybro, RFD900). Connect the ground unit to the PC via USB; configure UART baud rate (e.g. 57600 or 115200) in `config/app.yaml`.
- **LoRa Serial Transceivers (SX1262 / SX1276 / Ebyte E22):** Connect the ground transceiver module via a 3.3V USB-to-UART bridge (CP2102, FT232R) to `/dev/ttyUSB0` or `/dev/ttyACM0`. Ensure mode configuration pins (`M0=0, M1=0`) select transparent transmission mode.

#### 2. Air Data Rate & Bandwidth Sizing
- At the nominal 10 Hz telemetry rate, each 65-byte frame generates $650\text{ bytes/s}$ ($5,200\text{ bps}$) of raw payload.
- To prevent transmit buffer bloat, latency buildup, and packet loss on the radio modem FIFO:
  - Configure the modem's **Over-The-Air Data Rate** (Air Rate) to **$\ge 9,600\text{ bps}$** (or LoRa Spreading Factor $\text{SF}\le 7$, Bandwidth $\ge 250\text{ kHz}$, Coding Rate 4/5).
  - An air rate configured below $5,200\text{ bps}$ will cause modem FIFO overflow, manifesting as burst packet drops and triggering the dashboard's `PÉRDIDA DE PAQUETES` alarm badge.

#### 3. Antenna Sizing & Polarization Alignment
- **Vehicle Airframe:** Deploy an omnidirectional, vertically polarized 1/4-wave whip or dipole along the rocket fuselage or within a radio-transparent fiberglass nosecone.
- **Ground Station:** Deploy a matching vertically polarized high-gain antenna (e.g. ground plane collinear, or directional 3–5 element Yagi if operating beyond $2\text{ km}$ slant range). See [`docs/future-calculations.md`](future-calculations.md) Section 2.3 for antenna tracking calculations.

#### 4. Pre-Flight RF Ground Verification Checklist
1. **Device Enumeration:** Plug the ground radio into the PC and confirm device creation (`ls -l /dev/ttyUSB* /dev/ttyACM*`).
2. **Interface Alignment:** Confirm `port` and `baudrate` in `config/app.yaml` match the physical radio interface.
3. **Power-On Test:** Power on the rocket flight computer while stationary on the launch pad.
4. **Dashboard Link Health Check:**
   - Verify the dashboard header shows `● CONECTADO` with a steady 10.0 Hz RX rate.
   - Verify recent packet loss shows `0.0 %` and link health status displays `TODOS LOS SISTEMAS NOMINALES`.
   - Verify CRC error counter in Alarms shows zero (`ERRORES DE CRC DETECTADOS: 0`).
5. **Range & Attenuation Walk-Test:** Perform a ground walk-test around the launch perimeter to confirm adequate link margin ($> 15\text{ dB}$ margin or $\text{RSSI} > -95\text{ dBm}$) prior to flight arming.

---

## 7. Troubleshooting & Operational FAQ

| Problem / Log Message | Root Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'serial_asyncio'` (or `'fastapi'`) | Script was executed using system Python without activating the virtual environment, or packages were not installed. | Activate virtual environment: `source .venv/bin/activate` (Linux/macOS) or `.venv\Scripts\activate` (Windows). If `.venv` is missing, run: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`. |
| `PermissionError: [Errno 13] Permission denied: '/dev/ttyACM0'` | User does not have serial read/write access. | Run `sudo usermod -aG dialout $USER` and log out / log back in. |
| `FileNotFoundError: [Errno 2] No such file or directory: '/dev/ttyACM0'` | USB cable unplugged or wrong device name. | Verify connected devices with `ls /dev/tty*` and update `config/app.yaml`. The server will automatically keep retrying every 3 seconds. |
| `Address already in use` | Another instance of FastAPI or another process is using port 8000. | Stop the conflicting process or change `websocket.port` in `config/app.yaml`. |
| Dashboard shows `DESCONECTADO` (red dot) | Serial port disconnected or WebSocket dropped. | Check terminal server logs to see if UART opened; verify browser WebSocket connection in Network tab (`ws://localhost:8000/ws/telemetry`). |
| Dashboard shows `DEGRADADO` (amber dot) | No telemetry packet received for more than 1.5 seconds. | Check if transmitter is powered on and transmitting at expected baud rate. |
| CRC errors detected (`invalid > 0`) | Baud rate mismatch or electrical noise on RF link. | Ensure baud rate in `config/app.yaml` matches transmitter modem baud rate exactly (default: 115200). |

---

## 8. Related Documentation

- **[System Architecture & Component Documentation](architecture.md):** Complete data flow pipeline, `asyncio` concurrency, and decoupled frontend architecture.
- **[Frame Specification & Binary Protocol Reference](protocol.md):** 65-byte LoRa frame memory map, field data types, scales, and CRC-16 specification.
- **[Frame Schema Specification](frame-schema.md):** Declarative YAML frame definition reference and active production schema.
- **[Dashboard Visual Specification](frontend-dashboard.md):** Telemetry dashboard UI layout, visual hierarchy, and instrument wireframes.
- **[API & WebSocket Interface Specification](api.md):** REST endpoints, WebSocket schemas, connection lifecycle, and payload examples.
- **[Windows Executable Packaging](packaging-exe.md):** Compiling standalone Windows .exe using PyInstaller or GitHub Actions.
- **[Contributing Guide](../CONTRIBUTING.md):** Onboarding, Git workflow, testing requirements, and PR process.
- **[Extended Calculations & Future Reference](future-calculations.md):** Mathematical models for Kalman filtering, variometer ($V_z$), and antenna tracking.

