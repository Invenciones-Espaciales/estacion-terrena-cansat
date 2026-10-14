# Frame Specification & Binary Protocol Reference

This document provides the authoritative technical reference for the 29-byte telemetry binary frame transmitted by the rocket avionics and parsed by the Ground Station (`estacion-terrena-pc`).

---

## 1. Protocol Overview

The telemetry link uses a fixed-length, big-endian binary frame designed for robust transmission over low-bandwidth RF serial modems (e.g., LoRa, SiK, or XBee).

| Parameter | Specification | Reference in `config/frame.yaml` |
|---|---|---|
| **Frame Name** | Trama de Alta Frecuencia | `name: "Trama"` |
| **Protocol ID** | `0x01` | `id: 1` |
| **Total Frame Length** | 29 bytes | `frame.length: 29` |
| **Byte Ordering** | Big-Endian (Network Byte Order, MSB first) | `frame.byte_order: "big_endian"` |
| **Integrity Check** | CRC-16/CCITT-FALSE | `frame.crc.algorithm: "CRC-16/CCITT-FALSE"` |
| **CRC Location** | Bytes 27–28 (2 bytes) | `frame.crc.offset: 27`, `frame.crc.length: 2` |
| **CRC Calculation Range** | Bytes 0–26 inclusive (27 bytes) | `calculate_from: 0`, `calculate_to: 26` |
| **Transmission Rate** | 5 Hz nominal (configurable) | UART 115200 baud |
| **Raw Throughput** | 145 bytes/s (1,160 bps) | Requires RF modem Air Rate $\ge 2,400\text{ bps}$ |

---

## 2. 29-Byte Frame Memory Map

```text
Byte:   0    1    2    3    4    5    6    7    8    9   10   11   12   13   14
     ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐
     │ ID │TYPE│  SEQ_NUM │    TIMESTAMP      │  ACC_X  │  ACC_Y  │  ACC_Z  │ LAT│
     └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘
     
Byte:  15   16   17   18   19   20   21   22   23   24   25   26   27   28
     ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐
     │  LATITUDE │      LONGITUDE     │   ALT   │STAT│RSSI│SATS│  CRC-16  │
     └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘
```

---

## 3. Field Specification Reference

The table below reflects the exact schema configuration defined in `config/frame.yaml`.

| Offset | Length | Field Name | Binary Type | Endian | Scale Factor | Physical Offset | Engineering Unit | Raw Range | Physical / Value Range | Description |
|:---:|:---:|---|:---:|:---:|:---:|:---:|:---:|---|---|---|
| **0** | 1 | `rocket_id` | `uint8` | — | `1.0` | `0` | — | `0` to `255` | `0` to `255` | Unique identifier of the rocket airframe |
| **1** | 1 | `frame_type` | `uint8` | — | `1.0` | `0` | — | Expected: `0x01` | Fixed constant `0x01` | Frame type identifier; used to reject foreign packets |
| **2** | 2 | `frame_number` | `uint16` | Big | `1.0` | `0` | — | `0` to `65,535` | `0` to `65,535` | Rolling sequential counter used for packet loss tracking |
| **4** | 4 | `timestamp` | `uint32` | Big | `1.0` | `0` | `ms` | `0` to `4,294,967,295` | `0` to $4.29 \times 10^6$ s (~49.7 d) | Mission elapsed time / avionics boot time in milliseconds |
| **8** | 2 | `accel_x` | `int16` | Big | `0.001` | `0` | `g` | `-32,768` to `+32,767` | `-32.768` to `+32.767 g` | Transverse body X-axis acceleration ($1\text{ mg}$ resolution) |
| **10** | 2 | `accel_y` | `int16` | Big | `0.001` | `0` | `g` | `-32,768` to `+32,767` | `-32.768` to `+32.767 g` | Transverse body Y-axis acceleration ($1\text{ mg}$ resolution) |
| **12** | 2 | `accel_z` | `int16` | Big | `0.0005` | `0` | `g` | `-32,768` to `+32,767` | `-16.384` to `+16.3835 g` | Longitudinal thrust Z-axis acceleration ($0.5\text{ mg}$ resolution) |
| **14** | 4 | `latitude` | `int32` | Big | `0.000001` | `0` | `deg` | `±90,000,000` | `-90.000000°` to `+90.000000°` | GPS latitude ($10^{-6}$ degree / ~0.11 m resolution) |
| **18** | 4 | `longitude` | `int32` | Big | `0.000001` | `0` | `deg` | `±180,000,000` | `-180.000000°` to `+180.000000°` | GPS longitude ($10^{-6}$ degree resolution) |
| **22** | 2 | `altitude` | `int16` | Big | `1.0` | `0` | `m` | `-32,768` to `+32,767` | `-32,768` to `+32,767 m` | Geometric altitude above launch ground reference |
| **24** | 1 | `status` | `uint8` | — | `1.0` | `0` | — | `0x00` to `0xFF` | Discrete flight phases | Current vehicle state machine flight code (cumulative bitmask) |
| **25** | 1 | `rssi` | `int8` | — | `1.0` | `0` | `dBm` | `-128` to `+127` | `-128` to `+127 dBm` | Received signal strength indicator |
| **26** | 1 | `satellites` | `uint8` | — | `1.0` | `0` | — | `0` to `255` | `0` to `32` sats | Count of tracked GNSS satellites with active navigation fix |
| **27** | 2 | `crc` | `uint16` | Big | — | — | — | `0x0000` to `0xFFFF` | — | CRC-16/CCITT-FALSE calculated across bytes 0..26 (27 bytes) |

---

## 4. Vehicle Status Bitmask Definition

The `status` byte (offset 24) encodes mission milestones using a cumulative 8-bit flag system:

| Bit | Value | State Name | Description |
|:---:|:---:|:---|:---|
| — | `0x00` | `STANDBY` | Launchpad pre-launch idle & calibrated baseline |
| **Bit 0** | `0x01` (`1`) | `POWERED` | Motor ignited / Liftoff detected |
| **Bit 1** | `0x02` (`2`) | `BURNOUT` | Motor burnout / Ballistic ascent to apogee |
| **Bit 2** | `0x04` (`4`) | `APOGEE` | Apogee reached (maximum altitude) |
| **Bit 3** | `0x08` (`8`) | `DROGUE_ORD` | Pyro 1 trigger command issued (Drogue ejection) |
| **Bit 4** | `0x10` (`16`) | `DROGUE_CONF` | Drogue parachute deployment confirmed |
| **Bit 5** | `0x20` (`32`) | `MAIN_ORD` | Pyro 2 trigger command issued (Main parachute) |
| **Bit 6** | `0x40` (`64`) | `MAIN_CONF` | Main parachute deployment confirmed |
| **Bit 7** | `0x80` (`128`) | `LANDED` | Touchdown confirmed on ground (`0xFF`) |
