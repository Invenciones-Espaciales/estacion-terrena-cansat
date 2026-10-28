# CanSat CONAE Telemetry Protocol & Link Specification

This document provides the authoritative technical reference for the telemetry and telecommand protocol between the CanSat flight avionics and the Ground Station, in full compliance with **CONAE Bases §4–§7** and requirements **G1–G15, X1–X6, C3–C5, F1–F5**.

---

## 1. Protocol Overview

The CanSat communication architecture uses a bidirectional radio link operating in authorized Argentine ISM bands (915–928 MHz or 2.4 GHz, requirement X1) with point-to-point addressing (X2, no broadcast mode).

| Parameter | Specification | Official Requirement |
| :--- | :--- | :--- |
| **Transmission Rate** | 1 packet per second ($1\,\text{Hz}$) | **C5, X4** |
| **Format** | Comma-Separated Plain Text (ASCII CSV) | **CONAE Bases §4, G5** |
| **Mission Time Resolution** | $1\,\text{second}$ (UTC `hh:mm:ss`) | **G3, F2** |
| **Packet Sequence** | Monotonically increasing, persistent across reboots | **F1** |
| **Addressing** | Point-to-point with `TEAM_ID` prefix (`1000`) | **X2** |
| **Frequency Bands** | 915–928 MHz (ENACOM authorized license-free) | **X1** |
| **Uplink Commands** | ASCII formatted strings (`CMD,TEAM_ID,COMMAND`) | **G15, G1, F3, F5, X6** |
| **Dual CSV Output** | `Flight_XXXX.csv` (local notebook & backup storage) | **G2** |

---

## 2. Telemetry Frame Structure

Each telemetry frame is an ASCII string terminated by carriage return and newline (`\r\n` or `\n`):

```text
TEAM_ID, MISSION_TIME, PACKET_COUNT, MODE, STATE, ALTITUDE, TEMPERATURE, PRESSURE, VOLTAGE, CURRENT, GYRO_R, GYRO_P, GYRO_Y, ACCEL_R, ACCEL_P, ACCEL_Y, GPS_TIME, GPS_ALTITUDE, GPS_LATITUDE, GPS_LONGITUDE, GPS_SATS, CMD_ECHO [,,OPTIONAL_DATA]
```

### Field Definitions & Numerical Resolutions

| Index | Field Name | Type | Resolution / Units | Description & Official Mandate |
| :---: | :--- | :---: | :---: | :--- |
| 0 | `TEAM_ID` | String | 4 digits | Assigned Team Identification (e.g., `'1000'`). |
| 1 | `MISSION_TIME` | String | $1\,\text{s}$ (`hh:mm:ss`) | UTC mission time (**G3, F2**). |
| 2 | `PACKET_COUNT` | Integer | 1 packet | Total transmitted packets; persists across reboots (**F1**). |
| 3 | `MODE` | Char | `'F'` or `'S'` | Flight mode (`'F'`) or Simulation mode (`'S'`). |
| 4 | `STATE` | String | ASCII Enum | Operational software state: `'LAUNCH_PAD'`, `'ASCENT'`, `'APOGEE'`, `'DESCENT'`, `'PROBE_RELEASE'`, `'PAYLOAD_RELEASE'`, `'LANDED'`. |
| 5 | `ALTITUDE` | Float | $0.1\,\text{m}$ | Relative altitude to launchpad ground level (**X5**). |
| 6 | `TEMPERATURE` | Float | $0.1\,^\circ\text{C}$ | Ambient sensor temperature (**X5**). |
| 7 | `PRESSURE` | Float | $0.1\,\text{kPa}$ | Atmospheric sensor pressure (**X5**). |
| 8 | `VOLTAGE` | Float | $0.1\,\text{V}$ | Main bus battery voltage (**G7**). |
| 9 | `CURRENT` | Float | $0.01\,\text{A}$ | Battery discharge current draw (**G7**). |
| 10 | `GYRO_R` | Float | $0.1\,^\circ\text{/s}$ | Gyroscope Roll rate (**X5**). |
| 11 | `GYRO_P` | Float | $0.1\,^\circ\text{/s}$ | Gyroscope Pitch rate (**X5**). |
| 12 | `GYRO_Y` | Float | $0.1\,^\circ\text{/s}$ | Gyroscope Yaw rate (**X5**). |
| 13 | `ACCEL_R` | Float | $0.01\,\text{m/s}^2$ | Accelerometer Roll axis reading (**X5**). |
| 14 | `ACCEL_P` | Float | $0.01\,\text{m/s}^2$ | Accelerometer Pitch axis reading (**X5**). |
| 15 | `ACCEL_Y` | Float | $0.01\,\text{m/s}^2$ | Accelerometer Yaw axis reading (**X5**). |
| 16 | `GPS_TIME` | String | $1\,\text{s}$ (`hh:mm:ss`) | GPS receiver UTC time (**X5**). |
| 17 | `GPS_ALTITUDE` | Float | $0.1\,\text{m}$ | GPS altitude above mean sea level (**X5**). |
| 18 | `GPS_LATITUDE` | Float | $0.0001^\circ$ | Decimal degrees North (**X5**). |
| 19 | `GPS_LONGITUDE`| Float | $0.0001^\circ$ | Decimal degrees West (**X5**). |
| 20 | `GPS_SATS` | Integer | 1 satellite | Number of GPS satellites tracked (**X5**). |
| 21 | `CMD_ECHO` | String | ASCII text | Echo of last telecommand executed (**G15**). |
| 22 | `OPTIONAL_DATA`| String | Text after `,,` | Optional team-specific payload sensors (e.g. `SOLAR_V:4.85`). |

---

## 3. Telecommand Specification (Station $\to$ CanSat)

All telecommands sent from the Ground Station use the standard prefix `CMD,<TEAM_ID>,<ACTION>[,<ARGS>]\r\n`:

```text
CMD,1000,CAL\r\n
CMD,1000,ST,13:14:02\r\n
CMD,1000,PC,0\r\n
CMD,1000,BATT\r\n
CMD,1000,SIM,ENABLE\r\n
CMD,1000,START\r\n
```

### Telecommand Action Roadmap

| Command String | Execution Window | Action & Verification | Mandates |
| :--- | :--- | :--- | :--- |
| `CMD,1000,CAL` | On launchpad before launch | Calibrates relative altitude to zero ($h_0 = 0.0\,\text{m}$). CanSat sets `CMD_ECHO='CAL'`. | **G1, F5** |
| `CMD,1000,ST,<UTC>` | On launchpad before launch | Sets onboard RTC to within $\pm 1\,\text{s}$ of official UTC time. | **F3, F2** |
| `CMD,1000,PC,0` | On launchpad before launch | Resets persistent transmitted packet counter to zero. | **F1** |
| `CMD,1000,BATT` | Any mission phase | Queries battery state and solar panels; returned in telemetry. | **X6, G7** |
| `CMD,1000,SIM,ENABLE` | Pre-flight testing | Enables simulation mode; CanSat reports `MODE='S'`. | Bases §4 |
| `CMD,1000,START` | Rocket separation / Manual | Triggers mission state transition from `LAUNCH_PAD` to `ASCENT`/`DESCENT`. | **X3** |

---

## 4. Link Budget & Time-on-Air (ToA) Analysis

### 915 MHz LoRa Modulation Parameters
* **Carrier Frequency:** $915.0\,\text{MHz}$ (ENACOM authorized)
* **Bandwidth (BW):** $250\,\text{kHz}$
* **Spreading Factor (SF):** 7
* **Coding Rate (CR):** 4/5
* **Preamble:** 8 symbols

### Packet Size:
* Nominal ASCII frame length: $\sim 115\text{ to } 140\text{ bytes}$
* Binary payload equivalent: $65\text{ bytes}$

### Time-on-Air Calculation:
For $N = 130\text{ bytes}$ ASCII payload at SF7 / 250 kHz / CR 4/5:
$$\text{Symbol Duration } T_s = \frac{2^7}{250,000\,\text{Hz}} = 0.512\,\text{ms}$$
$$\text{Total Time on Air } \text{ToA} \approx 98.5\,\text{ms}$$

### Link Utilization at 1 Hz:
$$\text{Channel Duty Cycle} = \frac{98.5\,\text{ms}}{1000\,\text{ms}} \times 100\% = 9.85\%$$

> [!NOTE]
> Link utilization is under $10\%$, leaving $>900\,\text{ms}$ of idle channel time per second. This provides generous listening windows for half-duplex telecommand reception without packet collision.

---

## 5. Quantitative Link Health & Error Handling

1. **RX Packet Counter (`RX_COUNT`, G14):**
   Increments only when an incoming line is successfully parsed with $\ge 22$ valid fields.
2. **Packet Loss Calculation (`LOST_COUNT`, G8):**
   Tracked by monitoring gaps in the CanSat's persistent `PACKET_COUNT`:
   $$\text{If } \text{PACKET\_COUNT}_{k} > \text{PACKET\_COUNT}_{k-1} + 1 \implies \text{Lost} \mathrel{+}= \text{PACKET\_COUNT}_{k} - (\text{PACKET\_COUNT}_{k-1} + 1)$$
   $$\text{Loss Percentage} = \frac{\text{Lost}}{\text{RX\_COUNT} + \text{Lost}} \times 100\%$$
3. **Descent Velocity ($V_z$):**
   Computed on every packet:
   $$V_z = \frac{\text{ALTITUDE}_k - \text{ALTITUDE}_{k-1}}{t_k - t_{k-1}}$$
   - **Phase C3 Compliance:** $-18.0\,\text{m/s} \le V_z \le -12.0\,\text{m/s}$ ($15 \pm 3\,\text{m/s}$).
   - **Phase C4 Compliance:** $-8.0\,\text{m/s} \le V_z \le -2.0\,\text{m/s}$ ($5 \pm 3\,\text{m/s}$).
