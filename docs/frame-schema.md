# Generic Frame Definition Schema Specification

## 1. Objective

The Ground Station system dynamically parses and validates arbitrary binary telemetry frame formats without requiring any code modifications to the core application.

To accomplish this, each telemetry frame is declaratively defined using an external YAML configuration file ([`config/frame.yaml`](../config/frame.yaml)).

During runtime, the ground station engine:

1. Loads the YAML frame specification schema.
2. Ingests raw binary byte streams over the serial interface.
3. Identifies and validates candidate frame boundaries using configured lengths and CRC algorithms.
4. Extracts discrete fields according to byte offsets, lengths, and binary types.
5. Converts raw integer values to physical engineering metrics using linear scaling and offsets.
6. Maps discrete status codes to operational labels and delivers interpreted dictionaries to storage and WebSocket pipelines.

Modifying a vehicle's telemetry layout or adding new sensor fields requires only updating the YAML schema file—zero Python code changes are necessary.

---

# 2. Schema Structure

A declarative frame definition is structured into three primary sections:

```yaml
name: "Frame Name"
id: 1
description: "High-level description"

frame:
  length: 65
  byte_order: "little_endian"
  sync: "0xAA"

  crc:
    enabled: true
    algorithm: "CRC-16/CCITT-FALSE"
    polynomial: 0x1021
    initial_value: 0xFFFF
    final_xor: 0x0000
    reflect_input: false
    reflect_output: false
    offset: 63
    length: 2
    byte_order: "little_endian"
    calculate_from: 0
    calculate_to: 62

fields:
  - name: "sync"
    offset: 0
    length: 1
    type: "uint8"
    expected_value: 0xAA
  # Additional field definitions...
```

The schema consists of:
* **Identification Metadata:** Top-level protocol name, ID, and description.
* **General Frame Configuration:** Total length, byte ordering, synchronization byte, and CRC validation parameters.
* **Field Definitions:** Array of bit-level/byte-level telemetry channels with data types, scaling, and enumerations.

---

# 3. Identification Metadata

## `name`
Human-readable label for the telemetry frame:

```yaml
name: "Trama"
```

*Note: This is informational metadata; the parser does not use this field for routing.*

---

## `id`
Numeric protocol identifier for the frame:

```yaml
id: 1
```

Matches the protocol field identifying the packet type (e.g., `0x01` $\to$ High-frequency flight frame).

---

## `description`
Optional documentation string describing the intended purpose or mission phase:

```yaml
description: "Telemetría LoRa 65 bytes definitiva"
```

---

# 4. General Frame Configuration (`frame`)

The `frame` mapping defines packet-level transport properties.

```yaml
frame:
  length: 65
  byte_order: "little_endian"
  sync: "0xAA"
```

## `length`
Total byte length of the frame:

```yaml
length: 65
```

The sliding window parser uses this length to accumulate candidate slices from the serial byte stream before triggering integrity verification.

---

## `byte_order`
Defines default multi-byte endianness for fields that do not explicitly specify their own byte order.

Supported values:
- `"little_endian"` (Least Significant Byte first, standard on ARM/ESP32).
- `"big_endian"` (Most Significant Byte first, Network Byte Order).

Example: Two bytes `0x9F 0x01` in little-endian order represent $159 + 1 \times 256 = 415$.

---

## `sync`
Fixed synchronization marker byte or sequence (e.g. `"0xAA"`). When configured, the sliding byte window searches for this marker as the candidate frame boundary before validating length and CRC.

---

# 5. Cyclic Redundancy Check (`crc`)

The `crc` mapping defines the packet integrity verification parameters.

```yaml
crc:
  enabled: true
  algorithm: "CRC-16/CCITT-FALSE"
  polynomial: 0x1021
  initial_value: 0xFFFF
  final_xor: 0x0000
  reflect_input: false
  reflect_output: false

  offset: 63
  length: 2
  byte_order: "little_endian"

  calculate_from: 0
  calculate_to: 62
```

## `enabled`
Boolean flag indicating whether CRC verification is enforced (`true` or `false`).

## `algorithm`
Descriptive identifier for the algorithm (e.g. `"CRC-16/CCITT-FALSE"`).

## `polynomial`
CRC generator polynomial (e.g. `0x1021` for CCITT: $x^{16} + x^{12} + x^5 + 1$).

## `initial_value`
Pre-loaded register value prior to calculation (e.g. `0xFFFF`).

## `final_xor`
Value XORed with the register upon completion of calculation (e.g. `0x0000`).

## `reflect_input`
Boolean indicating if data bytes are processed LSB-first (`true`) or MSB-first (`false`).

## `reflect_output`
Boolean indicating if the final CRC value is bit-reversed before XOR (`true` or `false`).

## `offset`
Zero-indexed byte position where the CRC checksum is stored in the frame:
- `offset: 63` $\to$ Byte 63 is CRC LSB, Byte 64 is CRC MSB (in little-endian).

## `length`
Size of the CRC field in bytes (typically `2` for CRC-16).

## `byte_order`
Endianness of the transmitted checksum bytes (`"little_endian"` or `"big_endian"`).

## `calculate_from` and `calculate_to`
Inclusive byte indices defining the calculation range. For example:
- `calculate_from: 0`, `calculate_to: 62` computes the CRC over bytes 0 through 62 (63 total bytes). Bytes 63 and 64 contain the transmitted CRC and are excluded from the calculation.

---

# 6. Field Definitions (`fields`)

The `fields` list defines each telemetry metric embedded within the payload.

```yaml
fields:
  - name: "sync"
    offset: 0
    length: 1
    type: "uint8"
    expected_value: 0xAA
```

---

# 7. Field Properties Reference

### `name`
Internal identifier used by the application and emitted in JSON responses:
```yaml
name: "frame_number"
```
Parsed into Python dictionary key `data["frame_number"]`.

### `description`
Optional engineering description used for documentation and tooltips:
```yaml
description: "Sequential incremental frame ID (0..65535)"
```

### `offset`
Zero-indexed byte offset of the field within the frame:
```yaml
offset: 1
```

### `length`
Number of bytes occupied by the field:
```yaml
length: 2
```

### `type`
Binary data representation. Supported data types include:

| Type | Signedness | Size (bytes) | Description |
|---|:---:|:---:|---|
| `uint8` / `int8` | Unsigned / Signed | 1 | 8-bit integer |
| `uint16` / `int16` | Unsigned / Signed | 2 | 16-bit integer |
| `uint24` / `int24` | Unsigned / Signed | 3 | 24-bit integer |
| `uint32` / `int32` | Unsigned / Signed | 4 | 32-bit integer |
| `uint64` / `int64` | Unsigned / Signed | 8 | 64-bit integer |
| `float32` | Signed | 4 | IEEE 754 single-precision float |
| `float64` | Signed | 8 | IEEE 754 double-precision float |
| `bytes` | Raw | N | Hexadecimal string representation |

---

# 8. Physical Conversions & Scaling

### `scale`
Linear multiplier applied to convert raw integers into engineering units:
$$\text{Physical Value} = \text{Raw Integer} \times \text{scale}$$

Example for $0.1\text{ }^\circ\text{C}$ resolution:
```yaml
type: "int16"
scale: 0.1
unit: "°C"
```
A raw value of `185` decodes to $185 \times 0.1 = 18.5\text{ }^\circ\text{C}$.

### `offset_value`
Additive constant applied after scaling:
$$\text{Physical Value} = (\text{Raw Integer} \times \text{scale}) + \text{offset\_value}$$

Example:
```yaml
scale: 0.1
offset_value: -40.0
```
A raw value of `500` decodes to $(500 \times 0.1) - 40.0 = 10.0\text{ }^\circ\text{C}$.

### `unit`
Informational engineering unit symbol (e.g. `"g"`, `"Pa"`, `"m"`, `"deg"`, `"V"`, `"°C"`). Included in documentation and UI headers.

---

# 9. Enumerations & Expected Values

### `values`
Maps discrete integer codes to human-readable strings:

```yaml
- name: "status"
  offset: 7
  length: 1
  type: "uint8"
  values:
    0x00: "STANDBY"
    0x01: "POWERED"
    0x02: "BURNOUT"
    0x03: "BURNOUT"
    0x04: "APOGEE"
    0x07: "APOGEE"
    0x08: "DROGUE_ORD"
    0x0F: "DROGUE_ORD"
    0x10: "DROGUE_CONF"
    0x1F: "DROGUE_CONF"
    0x20: "MAIN_ORD"
    0x3F: "MAIN_ORD"
    0x40: "MAIN_CONF"
    0x7F: "MAIN_CONF"
    0x80: "LANDED"
    0xFF: "LANDED"
```

When raw code `0x01` is received:
- `data["status"] = 1`
- `data["status_label"] = "POWERED"`

### `expected_value`
Enforces packet filtering by requiring a specific field to match a fixed constant:

```yaml
- name: "sync"
  offset: 0
  length: 1
  type: "uint8"
  expected_value: 0xAA
```

If the received byte at offset 0 does not equal `0xAA`, the frame is rejected as invalid.

---

# 10. Active Production Schema (65-Byte LoRa Frame)

Below is the definitive 65-byte production configuration deployed in [`config/frame.yaml`](../config/frame.yaml):

```yaml
name: "Trama"
id: 1
description: "Telemetría LoRa 65 bytes definitiva"

frame:
  length: 65
  byte_order: "little_endian"
  sync: "0xAA"

  crc:
    enabled: true
    algorithm: "CRC-16/CCITT-FALSE"
    polynomial: 0x1021
    initial_value: 0xFFFF
    final_xor: 0x0000
    reflect_input: false
    reflect_output: false
    offset: 63
    length: 2
    byte_order: "little_endian"
    calculate_from: 0
    calculate_to: 62

fields:
  - name: "sync"
    offset: 0
    length: 1
    type: "uint8"
    expected_value: 0xAA

  - name: "frame_number"
    offset: 1
    length: 2
    type: "uint16"

  - name: "timestamp"
    offset: 3
    length: 4
    type: "uint32"
    unit: "ms"

  - name: "status"
    offset: 7
    length: 1
    type: "uint8"
    values:
      0x00: "STANDBY"
      0x01: "POWERED"
      0x02: "BURNOUT"
      0x03: "BURNOUT"
      0x04: "APOGEE"
      0x07: "APOGEE"
      0x08: "DROGUE_ORD"
      0x0F: "DROGUE_ORD"
      0x10: "DROGUE_CONF"
      0x1F: "DROGUE_CONF"
      0x20: "MAIN_ORD"
      0x3F: "MAIN_ORD"
      0x40: "MAIN_CONF"
      0x7F: "MAIN_CONF"
      0x80: "LANDED"
      0xFF: "LANDED"

  - name: "pressure"
    offset: 8
    length: 4
    type: "float32"
    unit: "hPa"

  - name: "altura_actual"
    offset: 12
    length: 4
    type: "float32"
    unit: "m"

  - name: "accel_x"
    offset: 16
    length: 4
    type: "float32"
    unit: "g"

  - name: "accel_y"
    offset: 20
    length: 4
    type: "float32"
    unit: "g"

  - name: "accel_z"
    offset: 24
    length: 4
    type: "float32"
    unit: "g"

  - name: "gyro_x"
    offset: 28
    length: 4
    type: "float32"
    unit: "deg/s"

  - name: "gyro_y"
    offset: 32
    length: 4
    type: "float32"
    unit: "deg/s"

  - name: "gyro_z"
    offset: 36
    length: 4
    type: "float32"
    unit: "deg/s"

  - name: "temp_imu"
    offset: 40
    length: 4
    type: "float32"
    unit: "°C"

  - name: "latitude"
    offset: 44
    length: 4
    type: "float32"
    unit: "deg"

  - name: "longitude"
    offset: 48
    length: 4
    type: "float32"
    unit: "deg"

  - name: "altitud_gps"
    offset: 52
    length: 4
    type: "float32"
    unit: "m"

  - name: "satellites"
    offset: 56
    length: 1
    type: "uint8"

  - name: "ground_speed"
    offset: 57
    length: 4
    type: "float32"
    unit: "m/s"

  - name: "pin_frenado"
    offset: 61
    length: 1
    type: "uint8"
    values:
      0: "DESACTIVADO"
      1: "ACTIVADO"

  - name: "pin_principal"
    offset: 62
    length: 1
    type: "uint8"
    values:
      0: "DESACTIVADO"
      1: "ACTIVADO"
```

---

# 11. Related Documentation

- **[System Architecture & Component Documentation](architecture.md):** Complete data flow pipeline, `asyncio` concurrency, and decoupled frontend architecture.
- **[Frame Specification & Binary Protocol Reference](protocol.md):** 65-byte frame memory map, field data types, scales, and CRC-16 specification.
- **[API & WebSocket Interface Specification](api.md):** REST endpoints, WebSocket schemas, connection lifecycle, and payload examples.
- **[Getting Started & Operations Guide](getting-started.md):** System configuration, Linux serial permissions, runtime operation, and verification testing.
- **[Dashboard Visual Specification](frontend-dashboard.md):** Dashboard layout, telemetry instruments, and ergonomic design guidelines.
- **[Project Entry Point & Index](../README.md):** Repository overview and documentation directory.
