# NASA-STD-3001 Telemetry Dashboard & Aerospace Cockpit Specification

> **Language / Idioma:** [ 🇬🇧 English ](frontend-dashboard.md) | [ 🇪🇸 Español ](es/frontend-dashboard.md)

## 1. Objective & Human-Systems Integration

The **Telemetry Ground Station** dashboard displays real-time sounding rocket telemetry strictly optimized for human situational awareness under high cognitive load.

The interface adheres to **NASA-STD-3001** (NASA Space Flight Human-System Standard) and **Mica Endsley’s Situation Awareness (SA) Model**, dividing information flow into three cognitive levels:
1. **Level 1 — Perception (Instantaneous State):** What is the vehicle doing *right now*? (Altitude, current G-load, angular rates, parachute deploy status).
2. **Level 2 — Comprehension (Temporal Evolution):** How are variables correlating over time? (Altitude vs GPS altitude, motor thrust vs burnout, vertical velocity vs ground speed).
3. **Level 3 — Projection (Recovery & Trajectory):** Where is the vehicle heading and where will it land? (Coordinates, distance and bearing vector to base station, GPS fix quality).

---

## 2. Desktop 5-Zone Cockpit Layout (100vw × 100vh — 0 Scroll)

On desktop displays ($\ge 901\text{ px}$, calibrated for $1366 \times 768$, $1280 \times 720$, and $1920 \times 1080$), the layout is locked to the viewport with **zero vertical or horizontal scrollbars**:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ ZONE 1: GLOBAL HEADER & LINK HEALTH (100% W × 42px H / ~8%)                            │
│ Brand • MET Clock • Phase • RSSI • IMU Temp • Packet Loss % • Link Status/Timer        │
├─────────────────────────┬───────────────────────────────┬──────────────────────────────┤
│ ZONE 2: PERCEPTION (25%)│ ZONE 3: COMPREHENSION (45%)   │ ZONE 4: PROJECTION (30%)     │
│ • Rolling Tape Alt      │ • 3 Stacked Time-Series Charts│ • Leaflet Satellite Map      │
│ • Mach Dip Divergence   │   - 50% H: Alt Baro vs GPS    │ • Trajectory Path Trace      │
│ • Pyrotechnic Blocks    │   - 25% H: Axial Accel (X)    │ • Base Guidance Vector       │
│ • Axial G-Meter + Peaks │   - 25% H: Speed & Vz         │ • GPS Fix Quality Banner     │
│ • Bipolar Gyro Bars     │ • Flight Phase Event Flags    │ • Signed Tabular Coordinates │
│ • Pressure & Accel XYZ  │ • Red Dashed Dropout Bridging │                              │
├─────────────────────────┴───────────────────────────────┴──────────────────────────────┤
│ ZONE 5: FLIGHT DECISION STRIP & EVENT LOG (100% W × 20% H)                             │
│ Flight Milestones Log (5fr) │ Active ISA-18.2 Alarms (5fr) │ CRC16 Link Diagnostics (2.5fr)│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Aerospace Instrument Specifications

### A. Altitude & Transonic Mach Dip Divergence Comparator
* **Rolling Tape Altimeter**: Vertical moving canvas displaying $\pm 100\text{ m}$ relative to current altitude with 10 m minor ticks and 50 m labeled major ticks.
* **Baro vs GPS Divergence**: Dual-stage comparator active during powered ascent (`POWERED`, `BURNOUT`) when GPS fix is acquired (`sats >= 4`):
  * **Normal ($|\Delta h| \le 30\text{ m}$)**: Neutral display.
  * **Warning ($30\text{ m} < |\Delta h| \le 60\text{ m}$)**: Amber badge (`.warn`).
  * **Transonic Critical Alert ($|\Delta h| > 60\text{ m}$)**: Flashing red alert (`.crit`) alerting the flight controller to the *transonic Mach dip* phenomenon, where dynamic pressure distortion momentarily compromises barometric readings.
* **Barometric Pressure**: Rendered as a secondary sub-label underneath altitude to avoid cluttering primary gauges.

### B. Axial G-Meter & Dual Peak Hold Tracking
* **Range**: $-2\text{ g}$ to $+12\text{ g}$ (14 g total dynamic span), centered with $0\text{ g}$ baseline at $14.3\%$ track height.
* **Dual Peak Hold**:
  * **Boost Peak (Amber, 2px horizontal line)**: Locks the maximum axial acceleration during motor thrust (`POWERED`, `BURNOUT`).
  * **Parachute Shock Peak (Cyan/Red, 2px horizontal line)**: Locks the peak opening shock upon drogue or main parachute deployment.
* **Tabular Linear Acceleration**: Mono-spaced signed table showing $A_x$, $A_y$, $A_z$ with explicit `+` and `−` signs (`+00.00 g`).

### C. Zero-Centered Bipolar Gyroscope Bars
* **Scale**: Linear horizontal bars spanning $-360^\circ/\text{s}$ to $+360^\circ/\text{s}$ with center at $0^\circ/\text{s}$ (positive fills right, negative fills left).
* **Thresholds & Visual Alerts**:
  * **Roll ($G_x$ Axial Spin)**: Amber warning at $> 180^\circ/\text{s}$.
  * **Pitch & Yaw ($G_y$, $G_z$ Tumbling)**: Amber warning at $> 180^\circ/\text{s}$, flashing red alert at $> 250^\circ/\text{s}$ to instantly identify vehicle dynamic instability.

### D. Cabin Pyrotechnic Annunciators (DROGUE & MAIN)
* **Design**: High-contrast binary flight blocks modeled on spacecraft annunciator panels.
* **State Behavior**:
  * `0` (Idle): Dark background (`#141414`), dotted gray border, muted text `[0: EN ESPERA]`.
  * `1` (Active/Fired): Solid high-contrast aerospace green (`#087a3b`), white text with `[OK] [1: DESPLEGADO]`.
* **Deployment Parity**: Present in both Telemetry Cockpit (`/`) and Recovery view (`/recovery`).

### E. Stacked Synchronized Time-Series with Dropout Visualization
* **Proportions**:
  * Top Chart (50% height): Barometric altitude (solid line) and GPS altitude (dotted line).
  * Middle Chart (25% height): Axial acceleration ($A_x$) to monitor motor burn and burnout.
  * Bottom Chart (25% height): Vertical velocity ($V_z$) and GPS ground speed.
* **Synchronization**: All 3 charts share an identical, synchronized 60-second horizontal time axis.
* **Event Flags**: Flight phase transitions automatically draw vertical dashed flag lines spanning across all 3 charts.
* **RF Dropout Visualization**: Packet silence $> 300\text{ ms}$ breaks continuous spline interpolation and bridges the gap with a thin red dashed line (`#ef4444`, `[3, 3]`), preventing synthetic data fabrication.

### F. Data Freezing Degradation (>300ms Silence)
* If packet reception pauses for $> 300\text{ ms}$ (3 lost packets at 10 Hz):
  * Dashboard data panels dim to $50\%$ opacity (`.stale-dim`).
  * Card headers display pulsing amber badges: `[CONGELADO]`.
  * Global header link status displays a live counter: `CONGELADO +X.Xs`.
* Returns immediately to normal brightness and live status upon arrival of the next valid packet.

### G. Recovery Navigation & Base Guidance Vector
* **Leaflet Map**: Renders vehicle GPS coordinates and color-graded trajectory polyline.
* **Base Guidance Vector**: Computes great-circle distance (meters / km) and true azimuth bearing ($000^\circ$ to $360^\circ$) from launch base to rocket.
* **GPS Fix Quality**: Border turns amber with `SIN FIX GPS` warning if satellites drop below 4.

---

## 4. Multi-View Header & Responsive Parity

All three views (`GO / NO-GO`, `TELEMETRÍA`, `RECUPERACIÓN`) share an identical **7-cell Global Header**:
1. `HORA LOCAL` (HH:MM:SS)
2. `TIEMPO DE MISIÓN` (T+ HH:MM:SS)
3. `FASE DE VUELO` (Spanish flight phase badge)
4. `SEÑAL RF (RSSI)` (dBm)
5. `TEMP. IMU` (Cockpit badge: normal $<45^\circ\text{C}$, warn $45\text{--}60^\circ\text{C}$, crit $>60^\circ\text{C}$)
6. `PÉRDIDA DE PAQUETES` (% over 5s sliding window)
7. `ENLACE` (Live status indicator with `CONGELADO +X.Xs` degradation timer)

### Mobile Adaptation ($\le 900\text{ px}$)
* Single-column responsive layout.
* Vertical scrolling cleanly enabled.
* **Zero horizontal overflow** (`scrollWidth == innerWidth`).
* Header wraps into clean 3-column / 2-column tabular grid.

---

## 5. Go / No-Go Cockpit Dashboard

The Go / No-Go view (`/gonogo`) implements a mission-readiness verification dashboard divided into:

1. **Hero Verdict Banner**:
   - High-contrast visual status (`GO` in emerald green `#10b981` or `NO-GO` in crimson `#ef4444`).
   - Quick action controls: `[🔒 Confirmar GO]` final authorization lock, `[📄 Exportar CSV]` audit log exporter, and `[🔄 Reiniciar]` checklist reset.
2. **4-Card Operational Matrix**:
   - **1. Comunicaciones**: Enlace salud, tasa efectiva Hz, pérdida en 5s, paquetes recibidos/perdidos, RSSI, CRC16, sensor stability timer, and micro-sparkline.
   - **2. Aviónica y Sensores**: Altitud en rampa, acelerómetro triaxial, GPS 3D fix & deriva en rampa, temp IMU, live stability timers with $\Delta\text{ máx}$, and micro-sparklines.
   - **3. Estación Terrena**: Puerto serie (`/dev/ttyACM0`), FastAPI/WebSocket service, SQLite DB logging, CSV logging, disk free percentage, and GPS rampa anchor coordinates.
   - **4. Checklist Manual**: Interactive tabular matrix of physical pre-launch checks (`Ítem`, `Responsable`, `Estado`, `Hora`) plus launchpad weather parameter verification.
3. **Bottom Diagnostic & Summary Panels**:
   - **Detalle de Verificaciones**: 4 aggregated readiness indicators (Comunicaciones, Aviónica, Estación, Checklist).
   - **Verificaciones Pendientes**: Real-time list of remaining unverified checklist tasks and out-of-tolerance sensor alerts.
   - **Resumen General**: Large status emblem with launch authorization advisory.
4. **Stability & Operator Authorization Model**:
   - Instead of a rigid global countdown, each sensor tracks continuous in-tolerance stability time in seconds with micro-sparklines and reset reasons.
   - The launch operator reviews stability and ticks off each system.
   - Verdict reaches `GO` when all system cards and all manual items are verified.
   - Every tick, untick, reset, and lock action is recorded in `state.auditLog` and downloadable as a CSV report.
