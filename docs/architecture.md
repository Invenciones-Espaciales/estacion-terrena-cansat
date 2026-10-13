# System Architecture & Component Documentation

This document describes the end-to-end system architecture, asynchronous concurrency model, data flow, and frontend rendering pipeline of the **Rocket Telemetry Ground Station** (`estacion-terrena-pc`).

---

## 1. System Overview

The Rocket Telemetry Ground Station is an asynchronous telemetry acquisition, validation, persistence, and real-time visualization platform. It receives binary telemetry streams from a rocket avionics transceiver over a serial interface (UART), parses and verifies packets dynamically against declarative YAML schemas, records flight data simultaneously to relational and flat-file storage, and streams decoded metrics to a low-latency web dashboard over WebSockets.

```mermaid
graph TD
    subgraph Hardware / Physical Layer
        AV[Rocket Avionics Transceiver] -->|RF Link| GSTR[Ground Station Receiver]
        GSTR -->|USB Serial /dev/ttyACM0| OS[Operating System Serial Driver]
    end

    subgraph Backend Core main.py
        OS -->|pyserial-asyncio| SP[SerialProtocol asyncio.Protocol]
        SP --> FB[FrameBuffer Byte Stream Accumulator]
        CFG[(config/frame.yaml)] -.-> FP[FrameParser Engine]
        FB --> FP
        FP -->|Decoded Dict| PF[process_frame Pipeline]
        
        PF --> DB[(SQLite Database telemetry.db)]
        PF --> CSV[(CSV Logger telemetry.csv)]
        PF --> STAT[PacketStatistics Tracker]
        PF --> WSM[WebSocketManager Broadcast Hub]
    end

    subgraph Presentation Layer frontend/index.html
        WSM -->|WebSocket ws://host:8000/ws/telemetry| WS_CLIENT[Client WebSocket Handler]
        WS_CLIENT --> STATE[Client Runtime State & Buffers]
        STATE --> RAF[requestAnimationFrame Render Engine]
        RAF --> TAPE[Canvas Altimeter Tape]
        RAF --> CHARTS[Canvas Time-Series Charts]
        RAF --> MAP[Leaflet GNSS Map & Polyline Track]
        RAF --> ALERTS[ISA-18.2 Alarm & Health Panel]
        RAF --> NUMS[High-Contrast Instrument Readouts]
    end
```

---

## 2. End-to-End Data Pipeline

The data ingestion path is engineered to decouple high-frequency byte stream acquisition from disk persistence and graphical rendering.

```mermaid
sequenceDiagram
    autonumber
    participant HW as Serial Port (/dev/ttyACM0)
    participant SER as SerialProtocol
    participant BUF as FrameBuffer
    participant PRS as FrameParser
    participant PROC as process_frame()
    participant DB as SQLite / CSV Storage
    participant WS as WebSocketManager
    participant UI as Frontend Dashboard

    HW->>SER: Raw byte chunk (data_received)
    SER->>BUF: feed(data)
    loop Buffer Processing
        BUF->>PRS: Validate length (30B) & CRC-16
        alt Frame Valid
            PRS-->>BUF: Parsed telemetry dict
            BUF->>PROC: Enqueue frame task
        else Frame Invalid
            PRS-->>BUF: None (resync sliding window)
        end
    end
    par Dual Persistence
        PROC->>DB: Insert row (SQLite & CSV flush)
    and Metrics Update
        PROC->>PROC: Update PacketStatistics
    and Real-Time Broadcast
        PROC->>WS: broadcast(telemetry_packet)
        WS->>UI: WebSocket JSON message
    end
    UI->>UI: Ingest into sliding buffers & redraw Canvas/Map
```

### 2.1 Serial Ingestion
- Telemetry enters via an asynchronous serial connection managed by `pyserial-asyncio` (`serial_asyncio.create_serial_connection`).
- The default interface is `/dev/ttyACM0` (Linux) or `COMx` (Windows) at `115200` baud.
- Low-level data chunks trigger `SerialProtocol.data_received(data: bytes)` on the active `asyncio` event loop without blocking thread execution.

#### 2.1.1 Physical RF Link & Radio Modems
- For wireless flight operations, the serial interface bridges directly to a physical RF transceiver (e.g. 433/915 MHz SiK modems or 868/915 MHz LoRa SX1262 modules).
- The radio modem operates in transparent serial streaming mode, passing binary frames across the air link into the host OS USB-UART driver without altering frame contents.
- Over-the-air data rate sizing ($\ge 9,600\text{ bps}$) is required to ensure 30-byte frames emitted at 10 Hz ($300\text{ bytes/s} = 2,400\text{ bps}$) pass through the modem's internal FIFO buffers without inducing transmit queues or packet drops (detailed in [`docs/getting-started.md`](getting-started.md#64-physical-rf-hardware-deployment--over-the-air-verification-lora--sik-radios)).


### 2.2 Framing and Sliding Synchronization
- Raw chunks are appended to a sliding byte buffer in `FrameBuffer`.
- If an explicit synchronization header (`sync`) is defined in the configuration, `FrameBuffer` scans for the sync byte sequence.
- When operating in sync-less fixed-frame mode (standard 30-byte frame), `FrameBuffer` inspects candidate 30-byte slices.
- If a candidate slice fails validation (invalid CRC or incorrect field structure), `FrameBuffer` discards one byte (`del buffer[0]`) and enters resynchronization mode, sliding through the stream until valid frame boundaries are recovered.

### 2.3 Declarative Parsing Engine
- `FrameParser` operates according to `config/frame.yaml`.
- The parser verifies:
  1. **Frame Length:** Validates exact 30-byte occupancy.
  2. **CRC-16/CCITT-FALSE Integrity:** Calculates CRC-16 over bytes 0 through 27 (polynomial `0x1021`, initial value `0xFFFF`, final XOR `0x0000`, no bit reflection). Compares the result with bytes 28–29.
  3. **Expected Values:** Verifies identity constants such as `frame_type == 0x01`.
  4. **Type Unpacking:** Translates binary fields according to their configured endianness (`big_endian`), extracting integers (`uint8`, `uint16`, `uint24`, `uint32`, `int16`, `int32`), floats, or byte vectors.
  5. **Physical Scaling & Offsets:** Applies linear formulas ($Physical = Raw \times Scale + Offset$).
  6. **Enumeration Translation:** Maps discrete status codes to operational human-readable labels (e.g., status code `2` maps to `Motor encendido / Ascenso`).

### 2.4 Dual Persistence Layer
Once parsed, `process_frame` records the packet simultaneously across two storage engines:
- **Relational SQLite Database (`data/telemetry.db`):**
  Records each packet in the `telemetry` table:
  ```sql
  CREATE TABLE IF NOT EXISTS telemetry (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp REAL NOT NULL,
      sequence INTEGER,
      payload TEXT NOT NULL
  );
  ```
  Indexed and queryable for post-flight telemetry analysis.
- **Flat-File CSV Logger (`data/telemetry.csv`):**
  Appends structured rows including the system timestamp, raw/scaled telemetry fields, and mapped label keys. Automatically writes headers upon file creation and flushes the buffer on every row write (`file.flush()`) to ensure no data loss occurs in the event of an abrupt power shutdown.

### 2.5 Real-Time WebSocket Broadcasting
- `WebSocketManager` maintains an active collection of connected browser clients (`set[WebSocket]`).
- Telemetry packets are formatted as JSON payloads containing the timestamp, packet statistics, CRC validation status, raw hex representation, and the parsed fields dictionary.
- Non-blocking concurrent broadcasting safely cleans up disconnected or broken client connections without disrupting the telemetry ingestion loop.

---

## 3. Concurrency and Asynchronous Model in `main.py`

The backend leverages Python's single-threaded cooperative multitasking model (`asyncio`) alongside **FastAPI** and **Uvicorn**, avoiding the thread-synchronization bottlenecks and race conditions common to multi-threaded serial pollers.

```mermaid
graph TD
    subgraph Single-Threaded asyncio Event Loop
        EL[asyncio Event Loop]
        
        subgraph Coroutines & Tasks
            T_SERIAL[serial_loop Task]
            T_HTTP[FastAPI / Starlette Route Handlers]
            T_WS[WebSocket Client Streaming Coroutines]
            T_PROC[process_frame Background Tasks]
        end

        subgraph Event Notifications
            CB_DATA[Protocol data_received Callback]
            CB_DISC[Protocol connection_lost Callback]
            EV_DISC[asyncio.Event: disconnected]
        end

        EL --> T_SERIAL
        EL --> T_HTTP
        EL --> T_WS
        EL --> T_PROC

        T_SERIAL -.->|Spawns| CB_DATA
        CB_DATA -.->|Schedules via create_background_task| T_PROC
        CB_DISC -.->|Signals| EV_DISC
        EV_DISC -.->|Wakes up| T_SERIAL
    end
```

### 3.1 Non-Blocking Protocol/Transport Architecture
- Instead of running a blocking `serial.read()` loop inside an OS thread, the application implements `asyncio.Protocol` (`SerialProtocol`).
- When the operating system signals that bytes are available on the serial port descriptor, `asyncio` triggers `SerialProtocol.data_received`.
- Windows compatibility is maintained by selecting `asyncio.WindowsSelectorEventLoopPolicy()` when running on Win32 platforms.

### 3.2 Resilient Background Task Management
- Frame processing and client broadcasting are offloaded using `create_background_task(coroutine)`.
- Background tasks are stored in a module-level set (`background_tasks: set[asyncio.Task]`) to prevent Python's garbage collector from destroying coroutines mid-execution.
- Done callbacks automatically remove completed tasks from the set and log unhandled exceptions.

### 3.3 Automatic Reconnection State Machine
- `serial_loop()` executes continuously in the background.
- If the serial port cannot be opened (e.g., the USB cable is unplugged), the loop logs a warning, sleeps for `reconnect_delay` seconds (default: 3 seconds), and retries.
- While the connection is active, `serial_loop()` awaits `protocol.disconnected.wait()`.
- Upon connection loss, `SerialProtocol.connection_lost()` sets the `disconnected` event and broadcasts a `{"type": "connection", "connected": false}` message to all dashboard clients.
- The web server remains fully operational and responsive even when the serial hardware is disconnected.

### 3.4 Graceful Lifespan Shutdown
- Upon application shutdown (`@app.on_event("shutdown")`), the runtime:
  1. Sets `runtime.connected = False`.
  2. Cancels all pending background tasks and gathers their completion via `asyncio.gather(*tasks, return_exceptions=True)`.
  3. Closes SQLite database connections.
  4. Flushes and closes open CSV log file descriptors.

---

## 4. Frontend Dashboard Architecture (`frontend/index.html`)

The frontend is a self-contained, high-contrast, zero-dependency telemetry console optimized for outdoor field visibility and sustained high-frequency operation.

```mermaid
graph TD
    subgraph Network Layer
        WS_STREAM[WebSocket /ws/telemetry]
        HTTP_POLL[HTTP GET /api/status Poll 5s]
    end

    subgraph State Ingestion & Sliding Buffers
        WS_STREAM --> INGEST[ingest message]
        HTTP_POLL --> LOAD_STATUS[loadStatus]
        INGEST --> HIST[state.hist 60s Sliding Window]
        INGEST --> SEQ_WIN[state.seqWindow 5s Loss Window]
        INGEST --> PKT_WIN[state.packetTimes 5s Rate Window]
        INGEST --> EVENTS[state.events Max 200 FIFO]
        INGEST --> ROUTE[state.routePoints Max 2000 FIFO]
    end

    subgraph Decoupled Render Engine loop now
        RAF[requestAnimationFrame Screen Refresh]
        RAF --> R_TAPE[drawTape: Exponential Smoothing]
        RAF --> R_CHARTS[renderCharts: Altitude & 3-Axis Accel]
        RAF -->|Throttled >= 33ms ~30Hz| R_TEXT[renderText: Numerical Metrics]
        RAF -->|Throttled >= 250ms 4Hz| R_SLOW[updateMap & renderLogs]
        RAF -->|Throttled >= 500ms 2Hz| R_HDR[renderHeader: Clocks & Health Dot]
    end
```

### 4.1 Decoupled Execution and Multi-Tiered Throttling
To prevent UI freezing, DOM thrashing, and memory degradation under high packet rates, the dashboard separates network message ingestion from visual rendering:
- **Network Ingestion (`ingest`):** Runs immediately upon packet arrival, updating numeric fields and appending points to in-memory buffers.
- **Render Engine (`requestAnimationFrame`):** Executes in synchronization with the browser display refresh rate, dispatching updates according to fixed time budgets:
  - **Every Frame (~60 Hz):**
    - `drawTape()`: Renders the dynamic Canvas altimeter tape using an exponential moving average (`altDisplay += (altitude - altDisplay) * 0.35`) for fluid mechanical animation.
    - `renderCharts()`: Repaints time-series Canvas charts with dynamic time-window extrapolation.
  - **~30 Hz ($\ge 33\text{ ms}$ interval):**
    - `renderText()`: Updates primary tabular text metrics (current altitude, max altitude, tri-axial acceleration).
  - **4 Hz ($\ge 250\text{ ms}$ interval):**
    - `updateMap()`: Pans Leaflet map and updates GPS polyline coordinates.
    - `renderLogs()`: Evaluates ISA-18.2 style alarms, maintains 5-second packet loss windows, computes instantaneous RX rate, and renders the flight events list.
  - **2 Hz ($\ge 500\text{ ms}$ interval):**
    - `renderHeader()`: Updates local clock, Mission Elapsed Time (MET `T+ HH:MM:SS`), flight stage badge, and connection health indicators.

### 4.2 Zero-Dependency High-Performance Canvas Rendering
Rather than loading third-party charting bundles, the dashboard renders charts directly to HTML5 Canvas:
- **Retina/HiDPI Scaling:** `fitCanvas()` inspects `window.devicePixelRatio`, adjusting the backing canvas buffer size while preserving CSS bounding dimensions to eliminate pixelation on high-DPI displays.
- **Continuous Sliding Time-Window:** Charts display a fixed 60-second historical window (`CFG.windowMs = 60000`). The right-hand time boundary is calculated by `chartEnd()` as the latest packet timestamp plus elapsed local time (clamped to 250 ms) to prevent visual stepping between frames.
- **Zero-Anchored Dynamic Auto-Scaling:** `niceRange()` guarantees that $0$ is always visible as a reference baseline with a dashed zero-line, while dynamically accommodating peak values.
- **Flight Event Annotations:** Flight phase transitions are rendered as vertical dashed marker lines with high-contrast text badges directly across the oscilloscope canvas.

### 4.3 Interactive GIS and Trajectory Mapping
- Powered by **Leaflet 1.9.4** and OpenStreetMap tiles.
- The launch point is permanently marked with a green anchor circle (`startMarker`).
- The real-time vehicle position is updated via `state.marker` and automatically panned.
- Vehicle track is drawn via an interactive polyline (`state.route`), updated at 2 Hz to avoid map DOM thrashing.

### 4.4 ISA-18.2 Style Operational Alarm System
The alarm subsystem continuously monitors mission safety criteria and classifies findings into standardized priority badges:
- **CRITICAL (`crit`, `#b00020`):**
  - Serial link loss / silence exceeding 3.0 seconds (`ENLACE PERDIDO`).
  - Recent packet loss exceeding 15% across a 5-second sliding window (`ALTA PÉRDIDA DE PAQUETES`).
- **WARNING (`warn`, `#f2b400`):**
  - Communication degradation / silence exceeding 1.5 seconds (`ENLACE DEGRADADO`).
  - Recent packet loss exceeding 5% (`PÉRDIDA MODERADA`).
  - G-force magnitude exceeding 9.5 g on any single axis (`ACELERACIÓN CERCANA AL LÍMITE`).
- **INFO (`info`, `#1a4fd6`):**
  - Frame corruption / CRC checksum failures detected (`ERRORES DE CRC DETECTADOS`).
- **STABLE (`ok`, `#087a3b`):**
  - All systems nominal (`TODOS LOS SISTEMAS NOMINALES`).

### 4.5 Memory-Safe Sliding Window Buffers
To prevent heap exhaustion during multi-hour rocket operations:
- **Historical Chart Metrics (`pushHist`):** Points older than 60,000 ms relative to the current timestamp are spliced out (`list.splice(0, removeCount)`).
- **Recent Packet Loss (`seqWindow`):** Sequence checks are evaluated over a 5,000 ms sliding window. Entries older than 5 seconds are purged.
- **Packet Reception Rate (`packetTimes`):** Rolling packet arrival timestamps are pruned beyond a 5-second window.
- **Capped FIFO Collections:**
  - Flight events log (`state.events`): Capped at 200 entries.
  - Phase chart markers (`state.markers`): Capped at 30 entries.
  - GPS trajectory polyline (`state.routePoints`): Capped at 2,000 coordinate pairs.
- Heap allocation remains flat and strictly bounded over indefinite runtimes.

---

## 5. Related Documentation

- **[Frame Specification & Binary Protocol Reference](protocol.md):** 30-byte frame memory map, field data types, scales, and CRC-16 specification.
- **[API & WebSocket Interface Specification](api.md):** REST endpoints, WebSocket schemas, connection lifecycle, and payload examples.
- **[Getting Started & Operations Guide](getting-started.md):** Setup, Linux serial permissions, runtime operation, and verification.
- **[Extended Calculations & Future Reference](calculos-futuros.md):** Mathematical models for Kalman filtering, variometer ($V_z$), and antenna tracking.
