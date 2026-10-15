# Mathematical Calculations and Derived Metrics Reference

> **Language / Idioma:** [ 🇬🇧 English ](future-calculations.md) | [ 🇪🇸 Español ](es/future-calculations.md)

This document serves as the technical specification for derived avionics metrics, sensor fusion filters, and mathematical algorithms temporarily retired from the live dashboard (`frontend/index.html`).

Currently, the primary dashboard displays **raw telemetry values directly as received in the binary frame** to ensure maximum reliability and minimal processing overhead during flight operations. All secondary interpretations and estimations are documented here for future reintegration.

> **Historical Reference Implementation:**
> The complete, operational JavaScript implementation containing these calculations is archived at [`docs/reference/index_with_calculations.html`](reference/index_with_calculations.html). It can be tested by serving it or copying it to `frontend/index.html` with the server running.

---

## 1. Primary Direct Telemetry Metrics (Current Dashboard)

The production dashboard renders telemetry directly from the parsed frame without algorithmic modification:

| Display Element | Frame Source Field | Engineering Units & Processing |
|---|---|---|
| **Altitude, Tape, Max Indicator, Chart** | `altitude` | Direct GPS/geometric altitude in meters ($m$) |
| **Barometer** | `pressure` | Atmospheric pressure converted from $\text{Pa}$ to $\text{hPa}$ ($\times 0.01$) |
| **Tri-Axial Acceleration ($a_x, a_y, a_z$)** | `accel_x`, `accel_y`, `accel_z` | Scaled acceleration in $g$ ($1\text{ mg}$ or $0.5\text{ mg}$ resolution) |
| **Position & Trajectory Polyline** | `latitude`, `longitude` | Micro-degrees scaled by $10^{-6}$ to decimal degrees ($^\circ$) |
| **Flight Phase & Chart Event Markers** | `status` | State machine codes mapped to `status_label` |
| **Mission Elapsed Time (MET)** | `timestamp` | Milliseconds formatted to `T+ HH:MM:SS` |
| **Link Diagnostics (Loss, Rate, CRC)** | `statistics` | Cumulative backend counters and 5-second sliding windows |
| **RF Diagnostics (RSSI, SNR, Voltage)** | `rssi`, `snr`, `voltage` | Displayed as `N/A` unless hardware and backend provide these optional fields |

> **Note on G-Load Card:**
> The dashboard retains one minimal mathematical readout: the instantaneous total G-force magnitude:
> $$G_{\text{total}} = \sqrt{a_x^2 + a_y^2 + a_z^2}$$
> along with peak value memory.

---

## 2. Extended Mathematical Calculations (Future Implementation)

### 2.1 Barometric Altitude & 1D Kalman Filter Fusion

#### Barometric Altitude Calculation
Barometric altitude is computed using the standard barometric formula referenced to ground conditions:
$$h_{\text{baro}} = h_0 + 44330 \times \left(1 - \left(\frac{p}{p_0}\right)^{0.190295}\right)$$
where $p_0$ and $h_0$ are the atmospheric pressure and GPS altitude recorded on the launch rail during the pre-launch baseline calibration.

#### 1D Kalman Filter (State: $[h, v]^T$)
Fuses barometric pressure (high frequency, low latency, sensor drift) with GPS altitude (low frequency, absolute accuracy) into a filtered altitude $h$ and vertical velocity $v$.

1. **State Vector & Transition Matrix:**
   $$\mathbf{x} = \begin{bmatrix} h \\ v \end{bmatrix}, \quad \mathbf{F} = \begin{bmatrix} 1 & \Delta t \\ 0 & 1 \end{bmatrix}$$
   where $\Delta t$ is the elapsed time between successive frames ($\Delta t \le 1.0\text{ s}$).

2. **Prediction Step:**
   $$\hat{\mathbf{x}}_{k|k-1} = \mathbf{F} \hat{\mathbf{x}}_{k-1|k-1}$$
   With acceleration process noise variance $q = 20\text{ (m/s²)}²$, covariance propagation is:
   $$P_{00} \leftarrow P_{00} + \Delta t (P_{10} + P_{01}) + \Delta t^2 P_{11} + \frac{q \Delta t^4}{4}$$
   $$P_{01} \leftarrow P_{01} + \Delta t P_{11} + \frac{q \Delta t^3}{2}, \quad P_{10} \leftarrow P_{01}$$
   $$P_{11} \leftarrow P_{11} + q \Delta t^2$$

3. **Sequential Measurement Updates ($\mathbf{H} = [1 \quad 0]$):**
   - **Barometric Update:** $R_{\text{baro}} = 4.0\text{ m}^2$ (applied at each packet arrival).
   - **GPS Update:** $R_{\text{GPS}} = 25.0\text{ m}^2$ (applied when new GPS fix arrives).
   - Innovation: $y = z - \hat{h}$
   - Kalman Gain: $\mathbf{K} = \frac{\mathbf{P} \mathbf{H}^T}{\mathbf{H} \mathbf{P} \mathbf{H}^T + R} = \frac{1}{P_{00} + R} \begin{bmatrix} P_{00} \\ P_{10} \end{bmatrix}$
   - State Correction: $\hat{\mathbf{x}} \leftarrow \hat{\mathbf{x}} + \mathbf{K} y$
   - Covariance Update: $\mathbf{P} \leftarrow (\mathbf{I} - \mathbf{K} \mathbf{H}) \mathbf{P}$

4. **Filter Reset:**
   The filter re-initializes to $\mathbf{x} = [h_{\text{GPS}}, 0]^T$ with $\mathbf{P} = \text{diag}(25, 25)$ if a packet timestamp retrograde jump is detected.

---

### 2.2 Variometer ($V_z$) & Total Velocity Vector

- **Vertical Velocity ($V_z$):** Directly extracted as the velocity state $v$ from the Kalman filter.
- **Horizontal Velocity ($V_h$):**
  - Calculated using Local Tangent Plane displacements over a sliding time window:
    $$V_x = \frac{x(t) - x(t - \delta t)}{\delta t}, \quad V_y = \frac{y(t) - y(t - \delta t)}{\delta t}$$
    with $\delta t \ge 1.0\text{ s}$ (spanning up to $4.0\text{ s}$) to filter out low-resolution GPS quantization steps.
  - Horizontal speed: $V_h = \sqrt{V_x^2 + V_y^2}$.
- **Total Velocity Magnitude:**
  $$\|V\| = \sqrt{V_z^2 + V_h^2}$$
- **Visualization:** A mechanical variometer tape scaled at $\pm 100\text{ m/s}$ with a colored needle indicator and dual-channel oscilloscope plotting $\|V\|$ and $V_z$ over time.

---

### 2.3 Ground Station Tracking (Azimuth, Elevation, Slant Range)

Calculates the line-of-sight pointing angles from the ground station antenna to the vehicle:

1. **Ground Station Reference:** Fixed at the initial valid launchpad GPS fix $(\text{lat}_0, \text{lon}_0, \text{alt}_0)$ or configured via URL query parameters (`?stlat=...&stlon=...&stalt=...`).
2. **Local Tangent Plane Coordinates (Flat-Earth Equirectangular Projection):**
   $$x = (\text{lon} - \text{lon}_0) \times 111320 \times \cos(\text{lat}_0)$$
   $$y = (\text{lat} - \text{lat}_0) \times 110540$$
   $$z = \text{alt} - \text{alt}_0$$
3. **Pointing Solutions:**
   - **Azimuth ($\theta_{\text{az}}$):** Clockwise angle from True North ($0^\circ \text{ to } 360^\circ$):
     $$\theta_{\text{az}} = \text{atan2}(x, y) \pmod{360^\circ}$$
   - **Elevation ($\phi_{\text{el}}$):** Angle above local horizon:
     $$\phi_{\text{el}} = \text{atan2}\left(z, \sqrt{x^2 + y^2}\right)$$
   - **Slant Range ($D$):** Euclidean distance in meters:
     $$D = \sqrt{x^2 + y^2 + z^2}$$
4. **Radar Polar Plot Display:**
   - Radial coordinate: $r = \frac{90^\circ - \phi_{\text{el}}}{90^\circ}$ (outer edge = horizon, center = zenith).
   - Angular coordinate: $\theta_{\text{az}}$ from True North.
   - Antenna directional lobe visualization with $\pm 10^\circ$ half-power beamwidth (`beamHalfWidthDeg`).

---

### 2.4 Parachute Impact Point Prediction Ellipse

Predicts the vehicle touchdown footprint during recovery descent:

- **Activation Trigger:** Evaluated when vehicle enters descent phase ($V_z < -2.0\text{ m/s}$) and Above Ground Level altitude ($\text{AGL} = h - h_0$) exceeds $5\text{ m}$.
- **Estimated Time-to-Impact:**
  $$t_{\text{impact}} = \frac{\text{AGL}}{-V_z}$$
- **Predicted Center of Impact:**
  $$\mathbf{p}_{\text{impact}} = \mathbf{p}_{\text{current}} + \begin{bmatrix} V_x \\ V_y \end{bmatrix} \times t_{\text{impact}}$$
- **Uncertainty Footprint (Dispersion Ellipse):**
  - Semi-major axis (oriented along track direction):
    $$a = \max(10\text{ m}, 0.15 \times V_h \times t_{\text{impact}})$$
  - Semi-minor axis (cross-track uncertainty):
    $$b = \max(10\text{ m}, 0.5 \times a)$$
- **Operational Assumptions:** Assumes constant descent velocity and ballistic translation without wind aloft drift gradient.

---

### 2.5 Vehicle Attitude & Incline Estimation

Approximates vehicle spatial orientation from static accelerometer vectors:
$$\text{Pitch} = \text{atan2}\left(a_x, \sqrt{a_y^2 + a_z^2}\right)$$
$$\text{Roll} = \text{atan2}(a_y, -a_z)$$
$$\text{Tilt Angle} = \text{atan2}\left(\sqrt{a_x^2 + a_y^2}, |a_z|\right)$$
- **Damping:** Filtered using exponential smoothing with factor $\alpha = 0.2$.
- **Operating Boundary:** Valid only in low-dynamic flight regimes (on launch rail or stable descent). During powered boost, thrust acceleration invalidates gravitational gravity-vector orientation.

---

### 2.6 Mechanical G-Meter Dial with Ghost Needle

- **Dial Scale:** Semicircular gauge calibrated from $0$ to $8\text{ g}_0$.
- **Ghost Needle Peak Retention:** Stores maximum acceleration and slowly decays at a constant rate of $2\text{ g/s}$:
  $$\text{ghost} = \max(g_{\text{current}}, \text{ghost} - 2.0 \times \Delta t)$$

---

### 2.7 ISA-18.2 Standard Alarm Engine

Implements an ANSI/ISA-18.2 compliant industrial alarm management state machine:

- **State Lifecycle:**
  1. *Normal* $\to$ Condition met $\to$ **Active Unacknowledged (UNACK)**
  2. **Active UNACK** $\to$ Operator Acknowledged $\to$ **Active Acknowledged (ACKED)**
  3. **Active UNACK** $\to$ Condition clears $\to$ **Returned Unacknowledged (RTN_UNACK)**
  4. **Active ACKED** $\to$ Condition clears $\to$ **Normal (Cleared)**
- **Alarm Definitions & Thresholds:**

| Alarm ID | Priority Level | Trigger Criteria | Normalization Condition |
|---|---|---|---|
| `LINK` | Critical (`CRIT`) | No serial connection or packet silence $> 3.0\text{ s}$ | Valid frame received |
| `DESC` | Critical (`CRIT`) | Phase $\ge \text{Descent}$, $V_z < -25\text{ m/s}$, $\text{AGL} \in [20, 300]\text{ m}$ | Velocity damped or touchdown |
| `GLOAD` | High (`WARN`) | Total acceleration $\|a\| > 8.0\text{ g}$ | $\|a\| \le 7.0\text{ g}$ |
| `CRC` | High (`WARN`) | Consecutive invalid CRC frames in last 10 seconds | 10 seconds without CRC errors |
| `VOLT` | High (`WARN`) | Avionics battery voltage $< 3.3\text{ V}$ | Voltage $\ge 3.5\text{ V}$ |
| `LOSS` | Medium (`INFO`) | Sliding 5-second packet loss $> 10\%$ | Packet loss $\le 5\%$ |
| `GPS` | Medium (`INFO`) | GPS fix lost ($\text{lat} = 0 \lor \text{lon} = 0$) | Valid GPS coordinates acquired |
| `RSSI` | Medium (`INFO`) | RF signal strength $< -100\text{ dBm}$ | Signal strength $\ge -95\text{ dBm}$ |

---

## 3. Target Display Refresh Rates

To ensure deterministic performance without browser render stalling, dashboard updates are organized into scheduled execution tiers:

| Subsystem | Target Frequency | Scheduling Mechanism |
|---|---|---|
| **Mission Clocks & Status Header** | 1–5 Hz | Throttled interval / RAF timer |
| **Primary Instruments (Altimeter Tape, Dial)** | 10–20 Hz (interpolated to 60 Hz) | `requestAnimationFrame` with exponential smoothing |
| **Time-Series Oscilloscopes** | 10 Hz (nominal frame rate) | Rendered upon telemetry arrival, synchronized with RAF |
| **GIS & Trajectory Mapping** | 1–5 Hz | Throttled Leaflet update loop |
| **Alarm Engine & Events Log** | Event-driven (evaluated at 4 Hz) | Batch processed to avoid DOM thrashing |

---

## 4. Engineering Roadmap & Implementation Checklist

When reintegrating these extended metrics, complete the following validation milestones:

- [ ] **Coordinate Frame Calibration:** Confirm accelerometer axis orientation against the flight airframe (in resting pad position, $a_z \approx -1.0\text{ g}$ or $+1.0\text{ g}$ depending on sensor orientation).
- [ ] **Aerodynamic Recovery Model:** Incorporate actual parachute drag coefficient ($C_d A$) and local wind aloft profile into the landing ellipse predictor.
- [ ] **Ground Station Location Management:** Provide a GUI modal or configuration parameter in `config/app.yaml` to configure ground station coordinates instead of relying on first fix or URL params.
- [ ] **Alarm Boundary Verification:** Calibrate alarm thresholds against historical flight telemetry datasets.
- [ ] **RF Metric Ingestion:** Extend `config/frame.yaml` and embedded avionics code to pack `rssi`, `snr`, and `voltage` telemetry fields.
- [ ] **Offline Tile Caching:** Package local map tile sets to support operations in remote launch sites lacking Internet connectivity.
- [ ] **Countdown Sequencer:** Add synchronized T-0 launch countdown sequencer to MET timer.

---

## 5. Related Documentation

- **[System Architecture Documentation](architecture.md):** Complete data flow pipeline and frontend render architecture.
- **[Frame Specification & Binary Protocol](protocol.md):** 65-byte LoRa telemetry frame structure and CRC-16 specification.
- **[Frame Schema Specification](frame-schema.md):** Declarative YAML frame definition reference and active production schema.
- **[Dashboard Visual Specification](frontend-dashboard.md):** Telemetry dashboard UI layout, visual hierarchy, and instrument wireframes.
- **[API & WebSocket Specification](api.md):** REST and WebSocket endpoints for ground station communication.
- **[Getting Started & Operations Manual](getting-started.md):** Setup, hardware configuration, and developer testing guide.
