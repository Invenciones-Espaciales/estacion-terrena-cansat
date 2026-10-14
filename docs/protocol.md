# Definitive 65-Byte LoRa Telemetry Frame Specification & Protocol Reference

This document provides the authoritative technical reference for the definitive **65-byte LoRa telemetry frame** transmitted by the rocket avionics (ESP32 / MCU) and parsed in real time by the Ground Station (`estacion-terrena-pc`).

---

## 1. Protocol & RF Link Overview

The telemetry link operates over a LoRa 433 MHz RF modulation channel configured for high-frequency transmission (10 Hz nominal rate) with deterministic Time on Air (ToA) and low buffer latency.

| Parameter | Specification | Reference in `config/frame.yaml` |
|---|---|---|
| **Frame Name** | Definitive LoRa Telemetry Frame | `name: "Trama"` |
| **Sync Byte** | `0xAA` (1 byte fixed header) | `frame.sync: "0xAA"` |
| **Total Frame Length** | 65 bytes | `frame.length: 65` |
| **Header Length** | 7 bytes (Sync, ID, Timestamp) | Offsets 0..6 |
| **Payload Length** | 56 bytes (Sensors & Actuators) | Offsets 7..62 |
| **Trailer Length** | 2 bytes (CRC-16) | Offsets 63..64 |
| **Byte Ordering** | Little-Endian (ESP32 IEEE-754 native) | `frame.byte_order: "little_endian"` |
| **Integrity Check** | CRC-16/CCITT-FALSE (Polynomial `0x1021`, Init `0xFFFF`) | `frame.crc.algorithm: "CRC-16/CCITT-FALSE"` |
| **CRC Location** | Bytes 63–64 (2 bytes) | `frame.crc.offset: 63`, `frame.crc.length: 2` |
| **CRC Calculation Range** | Bytes 0–62 inclusive (63 bytes) | `calculate_from: 0`, `calculate_to: 62` |
| **Transmission Rate** | 10 Hz (10 packets/second, 100 ms period) | Telemetry task loop |
| **Physical RF Bitrate** | 520 bits per frame | $65\text{ bytes} \times 8 = 520\text{ bits}$ |

---

## 2. LoRa RF Modulation & Time-on-Air (ToA) Budget

### RF Parameters:
* **Carrier Frequency:** 433 MHz
* **Bandwidth (BW):** 250 kHz ($250,000\text{ Hz}$)
* **Spreading Factor (SF):** 7
* **Coding Rate (CR):** 4/5
* **Preamble:** 8 symbols standard $+ 4.25$ synchronization margin

### Mathematical Calculations:
1. **Symbol Duration ($T_s$):**
   $$T_s = \frac{2^{\text{SF}}}{\text{BW}} = \frac{2^7}{250,000} = \frac{128}{250,000} = 0.512\text{ ms}$$

2. **Preamble Duration ($T_{\text{preamble}}$):**
   $$T_{\text{preamble}} = (8 + 4.25) \times 0.512\text{ ms} = 12.25 \times 0.512\text{ ms} = 6.27\text{ ms}$$

3. **Payload Duration ($T_{\text{payload}}$):**
   For a 65-byte payload with SF7, BW 250 kHz, and CR 4/5, the physical LoRa symbol count equals 108 symbols:
   $$T_{\text{payload}} = 108 \times 0.512\text{ ms} = 55.30\text{ ms}$$

4. **Total Time on Air (ToA):**
   $$\text{ToA} = T_{\text{preamble}} + T_{\text{payload}} = 6.27\text{ ms} + 55.30\text{ ms} = 61.57\text{ ms}$$

### Channel Capacity & Duty Cycle Analysis at 10 Hz:
* **Required Throughput (10 Hz):**
  $$\text{Throughput} = 520\text{ bits/frame} \times 10\text{ frames/s} = 5,200\text{ bps (5.20 kbps)}$$
* **Effective Link Capacity (SF7 / 250 kHz / CR 4/5):**
  $$\text{Useful Air Bitrate} \approx 10,937\text{ bps (10.94 kbps)}$$
* **Channel Duty Cycle / Channel Utilization:**
  $$\text{Duty Cycle} = \frac{5,200\text{ bps}}{10,937\text{ bps}} \times 100\% = 47.5\%$$
* **Safety Margin:**
  $$100\% - 47.5\% = 52.5\%\text{ free channel bandwidth}$$
* **Channel Idle Time per Cycle:**
  At a 10 Hz rate ($100\text{ ms}$ interval), the radio medium is silent for:
  $$100.00\text{ ms} - 61.57\text{ ms} = 38.43\text{ ms}$$
  This $38.43\text{ ms}$ silence window ensures complete ESP32 buffer flushing, zero transmitter queue saturation, immunity to clock drift, and robust RF receiver decoding.

---

## 3. 65-Byte Frame Memory Map

```text
Byte:   0    1    2    3    4    5    6    7    8    9   10   11   12   13   14   15
      ┌────┬─────────┬───────────────────┬────┬───────────────────┬───────────────────┐
      │SYNC│ SEQ_NUM │    TIMESTAMP      │STAT│  PRESSURE (BMP)   │ ALTURA_ACTUAL (m) │
      │0xAA│ uint16  │    uint32 (ms)    │uint│  float32 (hPa)    │   float32 (m)     │
      └────┴─────────┴───────────────────┴────┴───────────────────┴───────────────────┘

Byte:  16   17   18   19   20   21   22   23   24   25   26   27   28   29   30   31
      ┌───────────────────┬───────────────────┬───────────────────┬───────────────────┐
      │    ACCEL_X (g)    │    ACCEL_Y (g)    │    ACCEL_Z (g)    │   GYRO_X (deg/s)  │
      │    float32        │    float32        │    float32        │   float32         │
      └───────────────────┴───────────────────┴───────────────────┴───────────────────┘

Byte:  32   33   34   35   36   37   38   39   40   41   42   43   44   45   46   47
      ┌───────────────────┬───────────────────┬───────────────────┬───────────────────┐
      │   GYRO_Y (deg/s)  │   GYRO_Z (deg/s)  │   TEMP_IMU (°C)   │   LATITUDE (deg)  │
      │   float32         │   float32         │   float32         │   float32         │
      └───────────────────┴───────────────────┴───────────────────┴───────────────────┘

Byte:  48   49   50   51   52   53   54   55   56   57   58   59   60   61   62   63   64
      ┌───────────────────┬───────────────────┬────┬───────────────────┬────┬────┬─────────┐
      │  LONGITUDE (deg)  │  ALTITUD_GPS (m)  │SATS│ GROUND_SPEED(m/s) │PIN1│PIN2│ CRC-16  │
      │  float32          │  float32          │uint│ float32           │uint│uint│ uint16  │
      └───────────────────┴───────────────────┴────┴───────────────────┴────┴────┴─────────┘
```

---

## 4. Comprehensive Field Specification Table

All multi-byte integer and float fields are formatted in **Little-Endian** byte order:

| Byte Offset | Length | Field Name | Data Type | Endian | Scale | Unit | Description |
|:---:|:---:|---|:---:|:---:|:---:|:---:|---|
| **0** | 1 | `sync` | `uint8` | — | 1.0 | — | Synchronization byte fixed to `0xAA` for RF noise discrimination |
| **1..2** | 2 | `frame_number` | `uint16` | Little | 1.0 | — | Rolling packet sequence counter ($0\dots 65,535$) for loss calculation |
| **3..6** | 4 | `timestamp` | `uint32` | Little | 1.0 | `ms` | Flight elapsed time / avionics system `millis()` |
| **7** | 1 | `status` | `uint8` | — | 1.0 | — | Current vehicle flight stage bitmask / state machine code |
| **8..11** | 4 | `pressure` | `float32` | Little | 1.0 | `hPa` | Atmospheric pressure measured by BMP280 barometer |
| **12..15** | 4 | `altura_actual` | `float32` | Little | 1.0 | `m` | Barometric relative altitude calibrated against ground reference |
| **16..19** | 4 | `accel_x` | `float32` | Little | 1.0 | `g` | Linear IMU body acceleration on X-axis |
| **20..23** | 4 | `accel_y` | `float32` | Little | 1.0 | `g` | Linear IMU body acceleration on Y-axis |
| **24..27** | 4 | `accel_z` | `float32` | Little | 1.0 | `g` | Linear IMU thrust acceleration on Z-axis |
| **28..31** | 4 | `gyro_x` | `float32` | Little | 1.0 | `deg/s` | Angular velocity around X-axis from IMU gyroscope |
| **32..35** | 4 | `gyro_y` | `float32` | Little | 1.0 | `deg/s` | Angular velocity around Y-axis from IMU gyroscope |
| **36..39** | 4 | `gyro_z` | `float32` | Little | 1.0 | `deg/s` | Angular velocity around Z-axis from IMU gyroscope |
| **40..43** | 4 | `temp_imu` | `float32` | Little | 1.0 | `°C` | Internal temperature reading from IMU sensor die |
| **44..47** | 4 | `latitude` | `float32` | Little | 1.0 | `deg` | GPS latitude in decimal degrees |
| **48..51** | 4 | `longitude` | `float32` | Little | 1.0 | `deg` | GPS longitude in decimal degrees |
| **52..55** | 4 | `altitud_gps` | `float32` | Little | 1.0 | `m` | GPS geometric altitude above mean sea level (MSL) |
| **56** | 1 | `satellites` | `uint8` | — | 1.0 | — | Count of actively tracked GNSS satellites |
| **57..60** | 4 | `ground_speed` | `float32` | Little | 1.0 | `m/s` | Horizontal ground speed calculated by GNSS receiver |
| **61** | 1 | `pin_frenado` | `uint8` | — | 1.0 | — | Logic state of drogue/braking deployment pin (`0` = OFF, `1` = ACTIVE) |
| **62** | 1 | `pin_principal`| `uint8` | — | 1.0 | — | Logic state of main parachute deployment pin (`0` = OFF, `1` = ACTIVE) |
| **63..64** | 2 | `crc` | `uint16` | Little | — | — | CRC-16/CCITT-FALSE calculated across bytes 0 to 62 inclusive |

---

## 5. Flight State Machine Definition

The `status` byte (offset 7) represents the current flight phase:

| Code (Hex) | Name | Description |
|:---:|:---|:---|
| `0x00` | `STANDBY` | Launchpad pre-launch idle state & calibrated sensor baseline |
| `0x01` | `POWERED` | Motor ignited / Boost phase / Liftoff (T-0 detected) |
| `0x02` / `0x03` | `BURNOUT` | Motor burnout / Unpowered coasting ascent to apogee |
| `0x04` / `0x07` | `APOGEE` | Apogee reached (maximum altitude, zero vertical velocity) |
| `0x08` / `0x0F` | `DROGUE_ORD` | Pyro line 1 command issued (Drogue parachute ejection) |
| `0x10` / `0x1F` | `DROGUE_CONF` | Drogue parachute deployment confirmed; stable high-speed descent |
| `0x20` / `0x3F` | `MAIN_ORD` | Pyro line 2 command issued (Main parachute ejection at AGL threshold) |
| `0x40` / `0x7F` | `MAIN_CONF` | Main parachute confirmed; terminal low-speed descent |
| `0x80` / `0xFF` | `LANDED` | Touchdown confirmed on ground; radio beacons recovery coordinates |

---

## 6. C/C++ Firmware Implementation Example (ESP32)

Avionics firmware can define the packed frame structure directly in C++:

```cpp
#include <Arduino.h>

// Definitive 65-Byte Packed Telemetry Structure
struct __attribute__((packed)) LoRaPacket {
    // Header (7 bytes)
    uint8_t  sync;           // 0xAA fixed sync byte
    uint16_t frame_number;   // Packet sequence ID
    uint32_t timestamp;      // millis() since boot

    // Payload (56 bytes)
    uint8_t  status;         // Flight phase
    float    pressure;       // BMP280 barometric pressure (hPa)
    float    altura_actual;  // Calibrated relative altitude (m)
    float    accel_x;        // Linear acceleration X (g)
    float    accel_y;        // Linear acceleration Y (g)
    float    accel_z;        // Linear acceleration Z (g)
    float    gyro_x;         // Angular rate X (deg/s)
    float    gyro_y;         // Angular rate Y (deg/s)
    float    gyro_z;         // Angular rate Z (deg/s)
    float    temp_imu;       // IMU die temperature (°C)
    float    latitude;       // GPS latitude (decimal degrees)
    float    longitude;      // GPS longitude (decimal degrees)
    float    altitud_gps;    // GPS altitude ASL (m)
    uint8_t  satellites;     // Satellite count
    float    ground_speed;   // GPS ground speed (m/s)
    uint8_t  pin_frenado;    // 0: OFF, 1: ACTIVE
    uint8_t  pin_principal;  // 0: OFF, 1: ACTIVE

    // Trailer (2 bytes)
    uint16_t crc;            // CRC-16/CCITT-FALSE
};

// Verify struct size at compile time
static_assert(sizeof(LoRaPacket) == 65, "LoRaPacket must be exactly 65 bytes!");

// Standard CRC-16/CCITT-FALSE Calculation
uint16_t calculate_crc16(const uint8_t *data, size_t length) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < length; i++) {
        crc ^= ((uint16_t)data[i]) << 8;
        for (uint8_t bit = 0; bit < 8; bit++) {
            if (crc & 0x8000) {
                crc = (crc << 1) ^ 0x1021;
            } else {
                crc <<= 1;
            }
        }
    }
    return crc;
}

// Transmission Routine
void sendTelemetry(LoRaPacket &packet) {
    packet.sync = 0xAA;
    // Compute CRC over bytes 0..62 (63 bytes)
    packet.crc = calculate_crc16((const uint8_t*)&packet, 63);
    
    // Direct binary write to SX1278 LoRa radio
    LoRa.beginPacket();
    LoRa.write((const uint8_t*)&packet, sizeof(packet));
    LoRa.endPacket();
}
```
