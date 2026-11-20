# CONAE CanSat 2026–2027: Technical & Operational Requirements (Anexo A v2)

This document is the authoritative compliance reference for the **Ground Control Station (GCS)** based on **Anexo A v2 (G1–G15)** and the **PDR Scoresheet & FRR** evaluation criteria.

---

## 1. Technical & Operational Requirements (G1–G15)

| ID | Requirement | Specification | Code / System Status |
| :--- | :--- | :--- | :--- |
| **G1** | **Altitude Calibration** | Send a command to the CanSat to calibrate altitude to zero while on the launch pad before liftoff. | `POST /api/command` → `CMD,1000,CAL\r\n` |
| **G2** | **Data Logging & Backup** | Generate `.csv` files with all sensor data, recorded both on the ground station computer and on a backup drive. | `DualCSVLogger` → `data/Flight_1000.csv` & `data/backup/Flight_1000.csv` (`flush()` + `os.fsync()`) |
| **G3** | **Time Resolution** | Telemetry must include mission time with 1-second resolution (pre-synced within 1 s of UTC via ground command, per F3). | `MISSION_TIME` (`hh:mm:ss`, 1 Hz) + `CMD,1000,ST<HHMMSS>` |
| **G4** | **In-House Development** | Each team must develop its own ground station. | Custom Python/FastAPI backend (`main.py`) + HTML5/Canvas frontend (`frontend/index.html`) |
| **G5** | **Real-Time Text Display** | Display all telemetry in real-time text format during ascent and descent. | Live 1 Hz ASCII CSV terminal at bottom of `frontend/index.html` |
| **G6** | **SI Units** | Display all telemetry in the International System of Units (SI), explicitly indicating units on screen. | Explicit units (`m`, `°C`, `kPa`, `V`, `A`, `W`, `m/s²`, `°/s`, `m/s`) |
| **G7** | **Real-Time Plots** | Plot in real time: (1) Altitude, (2) Battery Voltage, (3) Battery Current, (4) 3-Axis Accelerometer, (5) 3-Axis Gyroscope. | 5 real-time HTML5 Canvas charts in `frontend/index.html` |
| **G8** | **Real-Time Status Indicators** | Display on screen: Mission Time, Temperature, GPS Position (lat, lon, alt, tracked sats per X5), RX Packet Count, Lost Packet Count, Flight Software State. | Header + status cards in `frontend/index.html` |
| **G9** | **Hardware & Autonomy** | Include a laptop with $\ge 2\text{ h}$ battery autonomy, a radio (ENACOM bands: 915–928 MHz or 2400–2483.5 MHz, no broadcast mode, per X1/X2), and an antenna. | Hardware / RF configuration (`config/app.yaml`, P2P `TEAM_ID`) |
| **G10** | **Portability & Power** | Fully portable for field operation along the flight line, without relying on AC power. | Portable laptop + USB transceiver |
| **G11** | **Antenna Type** | Use a tabletop or portable antenna. | Portable/tabletop antenna |
| **G12** | **Daylight Readability** | Design interface for intense sunlight visibility: large fonts (**minimum 14 pt**), bold chart traces and axes, dark text on light background. | Light theme (`#000000` on `#ffffff`/`#f1f5f9`), bold Canvas strokes (`lineWidth: 2` axes, `3` traces); **audit font sizes $\ge 14\text{ pt}$** |
| **G13** | **Tab-Free Interface** | Display all data simultaneously in the GUI; no tabs allowed. | Single-page zero-scroll CSS Grid (`frontend/index.html`) |
| **G14** | **True RX Packet Count** | Count successfully received packets at the ground station during flight (independent of CanSat TX counter). | `PacketStatistics` in `main.py` (`rx_count`, `lost_count`) |
| **G15** | **Telecommand Uplink** | Ability to transmit telecommands (including altitude calibration G1, UTC time sync F3, and battery/solar panel signal query X6). | Telecommand console in `frontend/index.html` → `POST /api/command` |

---

## 2. Additional Evaluation Criteria (PDR Scoresheet & FRR)

- **PDR Design Documentation:**
  - Context diagram (main components) and GCS design/connection diagram.
  - Antenna trade-off and selection (compare at least 2 options including radiation patterns, portable/tabletop mounting design, and justification).
  - GCS software design: screen prototypes, COTS packages used, real-time plotting design, calibration command transmission/verification method (barometer and roll/pitch angles), data recording, and `.csv` file generation for judges.
- **Pre-Flight On-Site Audit (FRR):**
  - Live verification with CanSat powered on: telemetry reception, real-time plots, and GUI data display.
  - Assigned radio frequency check to prevent interference.
