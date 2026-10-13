# Generic Frame Definition Schema Specification

## 1. Objective

The Ground Station system must dynamically parse and validate arbitrary binary telemetry frame formats without requiring any code modifications to the core application.

To accomplish this, each telemetry frame is declaratively defined using an external YAML configuration file (e.g., [`config/frame.yaml`](config/frame.yaml)).

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
  length: 30
  byte_order: "big_endian"

  crc:
    enabled: true
    algorithm: "CRC-16/CCITT-FALSE"
    polynomial: 0x1021
    initial_value: 0xFFFF
    final_xor: 0x0000
    reflect_input: false
    reflect_output: false
    offset: 28
    length: 2
    byte_order: "big_endian"
    calculate_from: 0
    calculate_to: 27

fields:
  - name: "rocket_id"
    offset: 0
    length: 1
    type: "uint8"
  # Additional field definitions...
```

The schema consists of:
* **Identification Metadata:** Top-level protocol name, ID, and description.
* **General Frame Configuration:** Total length, byte ordering, and CRC validation parameters.
* **Field Definitions:** Array of bit-level/byte-level telemetry channels with data types, scaling, and enumerations.

---

# 3. Identification Metadata

## `name`
Human-readable label for the telemetry frame:

```yaml
name: "High-Frequency Telemetry Frame"
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
description: "High-frequency sounding rocket telemetry stream"
```

---

# 4. General Frame Configuration (`frame`)

The `frame` mapping defines packet-level transport properties.

```yaml
frame:
  length: 30
  byte_order: "big_endian"
```

## `length`
Total byte length of the frame:

```yaml
length: 30
```

The sliding window parser uses this length to accumulate candidate slices from the serial byte stream before triggering integrity verification.

---

## `byte_order`
Defines default multi-byte endianness for fields that do not explicitly specify their own byte order.

Supported values:
- `"big_endian"` (Most Significant Byte first, Network Byte Order).
- `"little_endian"` (Least Significant Byte first).

Example: Two bytes `0x01 0x9F` in big-endian order represent $1 \times 256 + 159 = 415$.

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

  offset: 28
  length: 2
  byte_order: "big_endian"

  calculate_from: 0
  calculate_to: 27
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
- `offset: 28` $\to$ Byte 28 is CRC MSB, Byte 29 is CRC LSB.

## `length`
Size of the CRC field in bytes (typically `2` for CRC-16).

## `byte_order`
Endianness of the transmitted checksum bytes (`"big_endian"` or `"little_endian"`).

## `calculate_from` and `calculate_to`
Inclusive byte indices defining the calculation range. For example:
- `calculate_from: 0`, `calculate_to: 27` computes the CRC over bytes 0 through 27 (28 total bytes). Bytes 28 and 29 contain the transmitted CRC and are excluded from the calculation.

---

# 6. Field Definitions (`fields`)

The `fields` list defines each telemetry metric embedded within the payload.

```yaml
fields:
  - name: "rocket_id"
    offset: 0
    length: 1
    type: "uint8"
```

---

# 7. Field Properties Reference

### `name`
Internal identifier used by the application and emitted in JSON responses:
```yaml
name: "rocket_id"
```
Parsed into Python dictionary key `data["rocket_id"]`.

### `description`
Optional engineering description used for documentation and tooltips:
```yaml
description: "Rocket airframe identifier"
```

### `offset`
Zero-indexed byte offset of the field within the 30-byte frame:
```yaml
offset: 8
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
Informational engineering unit symbol (e.g. `"g"`, `"Pa"`, `"m"`, `"deg"`, `"V"`). Included in documentation and UI headers.

---

# 9. Enumerations & Expected Values

### `values`
Maps discrete integer codes to human-readable strings:

```yaml
- name: "status"
  offset: 27
  length: 1
  type: "uint8"
  values:
    0x00: "Standby"
    0x01: "Pre-launch"
    0x02: "Motor encendido / Ascenso"
    0x03: "Apogeo"
    0x04: "Descenso"
    0x05: "Aterrizaje"
```

When raw code `0x02` is received:
- `data["status"] = 2`
- `data["status_label"] = "Motor encendido / Ascenso"`

### `expected_value`
Enforces packet filtering by requiring a specific field to match a fixed constant:

```yaml
- name: "frame_type"
  offset: 1
  length: 1
  type: "uint8"
  expected_value: 0x01
```

If the received byte at offset 1 does not equal `0x01`, the frame is rejected as invalid.

---

# 10. Complete Production Example

Below is the standard production configuration utilized in `config/frame.yaml`:

```yaml
name: "Trama"
id: 1
description: "Telemetría de alta frecuencia"

frame:
  length: 30
  byte_order: "big_endian"

  crc:
    enabled: true
    algorithm: "CRC-16/CCITT-FALSE"
    polynomial: 0x1021
    initial_value: 0xFFFF
    final_xor: 0x0000
    reflect_input: false
    reflect_output: false

    offset: 28
    length: 2
    byte_order: "big_endian"

    calculate_from: 0
    calculate_to: 27

fields:

  - name: "rocket_id"
    description: "Identificador del cohete"
    offset: 0
    length: 1
    type: "uint8"

  - name: "frame_type"
    description: "Tipo de trama"
    offset: 1
    length: 1
    type: "uint8"
    expected_value: 0x01

  - name: "frame_number"
    description: "Número secuencial de trama"
    offset: 2
    length: 2
    type: "uint16"

  - name: "timestamp"
    description: "Tiempo desde el despegue"
    offset: 4
    length: 4
    type: "uint32"
    unit: "ms"

  - name: "accel_x"
    description: "Aceleración en eje X"
    offset: 8
    length: 2
    type: "int16"
    scale: 0.001
    offset_value: 0
    unit: "g"

  - name: "accel_y"
    description: "Aceleración en eje Y"
    offset: 10
    length: 2
    type: "int16"
    scale: 0.001
    offset_value: 0
    unit: "g"

  - name: "accel_z"
    description: "Aceleración en eje Z"
    offset: 12
    length: 2
    type: "int16"
    scale: 0.0005
    offset_value: 0
    unit: "g"

  - name: "pressure"
    description: "Presión atmosférica"
    offset: 14
    length: 3
    type: "uint24"
    scale: 1
    offset_value: 0
    unit: "Pa"

  - name: "latitude"
    description: "Latitud GPS"
    offset: 17
    length: 4
    type: "int32"
    scale: 0.000001
    offset_value: 0
    unit: "deg"

  - name: "longitude"
    description: "Longitud GPS"
    offset: 21
    length: 4
    type: "int32"
    scale: 0.000001
    offset_value: 0
    unit: "deg"

  - name: "altitude"
    description: "Altitud GPS"
    offset: 25
    length: 2
    type: "int16"
    scale: 1
    offset_value: 0
    unit: "m"

  - name: "status"
    description: "Estado actual del cohete"
    offset: 27
    length: 1
    type: "uint8"
    values:
      0x00: "Standby"
      0x01: "Pre-launch"
      0x02: "Motor encendido / Ascenso"
      0x03: "Apogeo"
      0x04: "Descenso"
      0x05: "Aterrizaje"
```

---

# 11. Related Documentation

- **[System Architecture & Component Documentation](docs/architecture.md):** Complete data flow pipeline, `asyncio` concurrency, and decoupled frontend architecture.
- **[Frame Specification & Binary Protocol Reference](docs/protocol.md):** 30-byte frame memory map, field data types, scales, and CRC-16 specification.
- **[API & WebSocket Interface Specification](docs/api.md):** REST endpoints, WebSocket schemas, connection lifecycle, and payload examples.
- **[Getting Started & Operations Guide](docs/getting-started.md):** System configuration, Linux serial permissions, runtime operation, and verification testing.
- **[Dashboard Visual Specification](front.md):** Dashboard layout, telemetry instruments, and ergonomic design guidelines.
- **[Project Entry Point & Index](README.md):** Repository overview and documentation directory.

