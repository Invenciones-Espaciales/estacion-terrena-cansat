# Telemetry Dashboard Design & Ergonomic Specification

## 1. Objective

The **Telemetry Ground Station** dashboard must display telemetry data clearly, compactly, and ergonomically for real-time monitoring during live rocket flight operations.

The user interface utilizes a responsive 12-column grid layout: 4-column metric panels across the top row, and adaptive-width panels across the lower rows sized to match their content density.

The core visual hierarchy is structured as follows:

* **Primary Metrics:** Large, high-contrast numeric values for immediate cognitive acquisition.
* **Link Health:** Critical communication and radio status persistently visible.
* **GPS & Spatial Tracking:** Grouped within a unified interactive map panel.
* **Flight Events:** High-priority stage transitions and milestone logging.

---

# 2. General Layout Architecture

The user interface is divided into three primary functional zones:

### Header
Spans the full display width across the top of the viewport.

Displays:
* System Title: `Estación Terrena` / `Ground Station`
* Mission Elapsed Time (MET): `T+ 00:03:42`
* Connection State Indicator: `● LINK CONNECTED`

Wireframe:
```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ HEADER — Ground Station                    T+ 00:03:42    ● LINK CONNECTED  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Primary Grid
A 12-column responsive layout:
- **Top Row (4 / 4 / 4):** Barometer, Altimeter, and Tri-Axial Accelerometer.
- **Bottom Row (6 / 3 / 3):** Interactive Map + Coordinates (6 columns), Link Health (3 columns), and Flight Milestones Log (3 columns).

Wireframe:
```text
┌──────────┬──────────┬──────────┐
│BAROMETER │ ALTITUDE │  ACCEL.  │
├──────────┼──────────┼──────────┤
│ MAP + COORDINATES   │HEALTH│LOG│
└─────────────────────┴──────┴───┘
```

This arrangement grants maximum visual prominence to the trajectory map without sacrificing telemetry density.

---

# 3. Barometer Instrument

Displays atmospheric pressure as a primary flight safety metric.

### Information Content
* Current barometric pressure (hPa)
* Rate of pressure change ($\Delta P$)
* Minimum recorded pressure
* Maximum recorded pressure

### Instrument Card Layout
```text
BAROMETER

        1008.42
          hPa

       ↓ 0.8 hPa

MIN     1006.12
MAX     1012.83
```

Current atmospheric pressure retains top visual weight, supplemented by a real-time sparkline or trend indicator.

---

# 4. Altimeter Instrument

Altitude is one of the most critical flight performance indicators.

### Information Content
* Current geometric altitude ($m$)
* Vertical velocity ($m/s$)
* Maximum apogee altitude reached ($m$)

### Instrument Card Layout
```text
ALTITUDE

       124.8
         m

       ↑ 2.4 m/s

MAX    181.2 m
```

The current altitude readout employs the largest typographic scale on the screen (42–48 px font size) alongside the mechanical moving altitude tape.

---

# 5. Tri-Axial Accelerometer Instrument

Displays acceleration across vehicle body axes ($X, Y, Z$).

### Information Content
* Transverse X-Axis ($g$)
* Transverse Y-Axis ($g$)
* Longitudinal Z-Axis ($g$)
* Total G-Load Vector Magnitude: $\sqrt{a_x^2 + a_y^2 + a_z^2}$

### Instrument Card Layout
```text
ACCELERATION

 X       +0.12 g
 Y       -0.03 g
 Z       +1.01 g
 ─────────────────
 MAGNITUDE  1.01 g
```

Total magnitude retains visual prominence over individual axis channels. Each axis is plotted in real-time on continuous Canvas oscilloscopes.

---

# 6. Radio Link Health & Diagnostics

Provides instantaneous operational visibility into serial link stability and RF packet delivery.

### Information Content
* Connection link status
* Latest received sequence number
* Total frames received
* Total frames lost
* Silence elapsed time since last packet
* Instantaneous reception rate (Hz)

### Instrument Card Layout
```text
LINK HEALTH

● CONNECTED

SENT (SEQ)       18,452
RECEIVED         18,449
LOST                  3

LAST PACKET       0.1 s
RX RATE          10.0 Hz
```

### Visual State Indication

| Status | Dot Color | Condition |
|---|:---:|---|
| **Connected** | Green | Active packet ingestion within nominal timing |
| **Degraded** | Amber | Silence $> 1.5\text{ s}$ or packet loss $> 5\%$ |
| **Disconnected** | Red | Hardware UART closed or silence $> 3.0\text{ s}$ |

---

# 7. Interactive GIS & Trajectory Map

Occupies a prominent **6/12 column** panel.

### Information Content
* Real-time vehicle coordinates
* Historical trajectory polyline
* Launchpad coordinate anchor (`startMarker`)
* Georeferenced flight event markers

### Map Card Layout
```text
GPS / MAP

┌─────────────────────────────────────────────┐
│                     MAP                     │
│                 ●────●                      │
│                                             │
├─────────────────────────────────────────────┤
│ LATITUDE                LONGITUDE           │
└─────────────────────────────────────────────┘
```

Implemented with **Leaflet 1.9.4** and OpenStreetMap cartography. Panned and refreshed at throttled intervals (4 Hz) to prevent DOM thrashing.

---

# 8. Flight Milestones & State Transition Log

Records and displays vehicle flight state changes.

Transitions are captured as **Flight Stage + Mission Elapsed Time**. Technical network errors and CRC logs are routed to diagnostic alerts rather than cluttering this operational log.

### Event Log Layout
```text
FLIGHT EVENTS

09:42:13    PRE-LAUNCH
09:42:48    POWERED ASCENT
09:43:12    APOGEE
09:43:41    PARACHUTE DESCENT
09:44:02    TOUCHDOWN
```

The header permanently highlights the active operational phase:
```text
CURRENT
POWERED ASCENT
```

---

# 9. Geolocation Coordinate Readouts

Coordinates are rendered in a dedicated numeric readout panel adjacent to the map:
* **Latitude:** Signed decimal degrees ($^\circ$, 6 decimal places)
* **Longitude:** Signed decimal degrees ($^\circ$, 6 decimal places)

---

# 10. Visual Hierarchy & Ergonomic Principles

The console prioritizes telemetry metrics according to operational criticality:

1. **Link Health & Radio Connection**
2. **Current Altitude & Apogee**
3. **Vehicle Position & Track**
4. **Tri-Axial Acceleration & Peak G-Load**
5. **Barometric Pressure**
6. **Flight Phase Transitions**
7. **GNSS Coordinate Readouts**

Primary values utilize bold, high-contrast typography, while secondary metrics use subdued scales to avoid visual fatigue under sunlight conditions.

---

# 11. Core Design Guidelines

### High Information Density
Presents high-dimensional telemetry without degrading into an unreadable tabular spreadsheet.

### Predictable Layout Stability
Dynamic updates must never induce layout shifting, jitter, or scroll jumps.

### Sunlight Readability (Field Conditions)
High-contrast color palette, minimum 14 pt font sizes for critical readouts, and prominent canvas stroke widths designed for outdoor operation under direct solar illumination.

### Extensible Modular Architecture
Structured to accommodate future telemetry cards (variometer, antenna radar, battery voltage, temperature) without disrupting core dashboard stability.

---

# 12. Related Documentation

- **[System Architecture & Component Documentation](docs/architecture.md):** Complete data flow pipeline, `asyncio` concurrency, and decoupled frontend architecture.
- **[Frame Specification & Binary Protocol Reference](docs/protocol.md):** 30-byte frame memory map, field data types, scales, and CRC-16 specification.
- **[API & WebSocket Interface Specification](docs/api.md):** REST endpoints, WebSocket schemas, connection lifecycle, and payload examples.
- **[Getting Started & Operations Guide](docs/getting-started.md):** System configuration, Linux serial permissions, runtime operation, and verification testing.
- **[Frame Schema Specification](config.md):** Declarative YAML frame definition reference.
- **[Project Entry Point & Index](README.md):** Repository overview and documentation directory.

