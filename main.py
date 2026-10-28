"""CanSat CONAE Ground Station Core Application.

Asynchronous FastAPI service for real-time CanSat telemetry acquisition,
validation, dual CSV persistence (G2), SQLite indexing, telecommand dispatch (G15),
and WebSocket broadcasting for the high-contrast single-window dashboard (G13).
"""

from __future__ import annotations

import asyncio
import csv
import datetime
import json
import logging
import os
import shutil
import sqlite3
import struct
import sys
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import serial_asyncio
    import uvicorn
    import yaml
    from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
except ModuleNotFoundError as exc:
    missing_mod = exc.name or "required dependencies"
    sys.stderr.write(
        "\n====================================================================\n"
        f"[ERROR] Missing required dependency: '{missing_mod}'\n"
        "The Ground Station requires packages installed in the virtual environment.\n\n"
        "To resolve this issue:\n"
        "  1. Activate the project virtual environment:\n"
        "       source .venv/bin/activate       # On Linux / macOS\n"
        "       .venv\\Scripts\\activate          # On Windows\n\n"
        "  2. Re-run:\n"
        "       python main.py\n"
        "====================================================================\n\n"
    )
    sys.exit(1)

# ============================================================
# WINDOWS / ASYNCIO COMPATIBILITY
# ============================================================

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ============================================================
# PATHS & RUNTIME ENVIRONMENT
# ============================================================

IS_FROZEN = getattr(sys, "frozen", False)

if IS_FROZEN:
    APP_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = APP_DIR

BASE_DIR = APP_DIR
DATA_DIR = APP_DIR / "data"
BACKUP_DIR = DATA_DIR / "backup"

CONFIG_DIR = APP_DIR / "config" if (APP_DIR / "config").exists() else (BUNDLE_DIR / "config")
FRONTEND_DIR = APP_DIR / "frontend" if (APP_DIR / "frontend").exists() else (BUNDLE_DIR / "frontend")

APP_CONFIG_FILE = CONFIG_DIR / "app.yaml"
FRAME_CONFIG_FILE = CONFIG_DIR / "frame.yaml"

DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("telemetry")

# ============================================================
# CANSTAT TELEMETRY DATA STRUCTURES (CONAE SPECIFICATION)
# ============================================================

CANSAT_FIELDS = [
    "TEAM_ID",
    "MISSION_TIME",
    "PACKET_COUNT",
    "MODE",
    "STATE",
    "ALTITUDE",
    "TEMPERATURE",
    "PRESSURE",
    "VOLTAGE",
    "CURRENT",
    "GYRO_R",
    "GYRO_P",
    "GYRO_Y",
    "ACCEL_R",
    "ACCEL_P",
    "ACCEL_Y",
    "GPS_TIME",
    "GPS_ALTITUDE",
    "GPS_LATITUDE",
    "GPS_LONGITUDE",
    "GPS_SATS",
    "CMD_ECHO",
]

VALID_STATES = {
    "LAUNCH_PAD": "LAUNCH_PAD",
    "ASCENT": "ASCENT",
    "APOGEE": "APOGEE",
    "DESCENT": "DESCENT",
    "PROBE_RELEASE": "PROBE_RELEASE",
    "PAYLOAD_RELEASE": "PAYLOAD_RELEASE",
    "LANDED": "LANDED",
    # Legacy fallbacks
    "STANDBY": "LAUNCH_PAD",
    "POWERED": "ASCENT",
    "BURNOUT": "ASCENT",
    "DROGUE_CONF": "DESCENT",
    "MAIN_CONF": "DESCENT",
}

@dataclass
class CanSatTelemetry:
    team_id: str
    mission_time: str
    packet_count: int
    mode: str
    state: str
    altitude: float
    temperature: float
    pressure: float
    voltage: float
    current: float
    gyro_r: float
    gyro_p: float
    gyro_y: float
    accel_r: float
    accel_p: float
    accel_y: float
    gps_time: str
    gps_altitude: float
    gps_latitude: float
    gps_longitude: float
    gps_sats: int
    cmd_echo: str
    optional_data: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Uppercase canonical keys for CONAE compliance & dashboard consumption
        mapped = {
            "TEAM_ID": self.team_id,
            "MISSION_TIME": self.mission_time,
            "PACKET_COUNT": self.packet_count,
            "MODE": self.mode,
            "STATE": self.state,
            "ALTITUDE": self.altitude,
            "TEMPERATURE": self.temperature,
            "PRESSURE": self.pressure,
            "VOLTAGE": self.voltage,
            "CURRENT": self.current,
            "GYRO_R": self.gyro_r,
            "GYRO_P": self.gyro_p,
            "GYRO_Y": self.gyro_y,
            "ACCEL_R": self.accel_r,
            "ACCEL_P": self.accel_p,
            "ACCEL_Y": self.accel_y,
            "GPS_TIME": self.gps_time,
            "GPS_ALTITUDE": self.gps_altitude,
            "GPS_LATITUDE": self.gps_latitude,
            "GPS_LONGITUDE": self.gps_longitude,
            "GPS_SATS": self.gps_sats,
            "CMD_ECHO": self.cmd_echo,
            "OPTIONAL_DATA": self.optional_data,
            # Lowercase mirrors for backward compatibility with existing frontends
            "altura_actual": self.altitude,
            "temp_imu": self.temperature,
            "pressure_raw": self.pressure,
            "accel_x": self.accel_r,
            "accel_y": self.accel_p,
            "accel_z": self.accel_y,
            "gyro_x": self.gyro_r,
            "gyro_y": self.gyro_p,
            "gyro_z": self.gyro_y,
            "altitud_gps": self.gps_altitude,
            "latitude": self.gps_latitude,
            "longitude": self.gps_longitude,
            "satellites": self.gps_sats,
            "status": self.state,
            "frame_number": self.packet_count,
        }
        return mapped

    def to_csv_row(self) -> str:
        base = [
            str(self.team_id),
            str(self.mission_time),
            str(self.packet_count),
            str(self.mode),
            str(self.state),
            f"{self.altitude:.1f}",
            f"{self.temperature:.1f}",
            f"{self.pressure:.1f}",
            f"{self.voltage:.1f}",
            f"{self.current:.2f}",
            f"{self.gyro_r:.1f}",
            f"{self.gyro_p:.1f}",
            f"{self.gyro_y:.1f}",
            f"{self.accel_r:.1f}",
            f"{self.accel_p:.1f}",
            f"{self.accel_y:.1f}",
            str(self.gps_time),
            f"{self.gps_altitude:.1f}",
            f"{self.gps_latitude:.4f}",
            f"{self.gps_longitude:.4f}",
            str(self.gps_sats),
            str(self.cmd_echo).replace(",", ""),
        ]
        if self.optional_data:
            return ",".join(base) + ",," + str(self.optional_data)
        return ",".join(base)


# ============================================================
# CANSTAT ASCII CSV PARSER
# ============================================================

class CanSatAsciiParser:
    """Parses plain-text comma-separated CanSat telemetry frames."""

    @staticmethod
    def parse_line(line_str: str) -> Optional[CanSatTelemetry]:
        line = line_str.strip()
        if not line or line.startswith("#"):
            return None

        # Handle optional data separated by double comma (,,)
        optional_data = ""
        if ",," in line:
            parts = line.split(",,", 1)
            main_csv = parts[0]
            optional_data = parts[1]
        else:
            main_csv = line

        tokens = [t.strip() for t in main_csv.split(",")]
        if len(tokens) < 22:
            logger.warning("CanSat line has insufficient fields: %d (expected >= 22)", len(tokens))
            return None

        try:
            team_id = tokens[0]
            mission_time = tokens[1]
            packet_count = int(tokens[2])
            mode = tokens[3].upper()
            state_raw = tokens[4].upper()
            state = VALID_STATES.get(state_raw, state_raw)

            altitude = float(tokens[5])
            temperature = float(tokens[6])
            pressure = float(tokens[7])
            voltage = float(tokens[8])
            current = float(tokens[9])

            gyro_r = float(tokens[10])
            gyro_p = float(tokens[11])
            gyro_y = float(tokens[12])

            accel_r = float(tokens[13])
            accel_p = float(tokens[14])
            accel_y = float(tokens[15])

            gps_time = tokens[16]
            gps_altitude = float(tokens[17])
            gps_latitude = float(tokens[18])
            gps_longitude = float(tokens[19])
            gps_sats = int(tokens[20])

            cmd_echo = tokens[21]

            return CanSatTelemetry(
                team_id=team_id,
                mission_time=mission_time,
                packet_count=packet_count,
                mode=mode,
                state=state,
                altitude=altitude,
                temperature=temperature,
                pressure=pressure,
                voltage=voltage,
                current=current,
                gyro_r=gyro_r,
                gyro_p=gyro_p,
                gyro_y=gyro_y,
                accel_r=accel_r,
                accel_p=accel_p,
                accel_y=accel_y,
                gps_time=gps_time,
                gps_altitude=gps_altitude,
                gps_latitude=gps_latitude,
                gps_longitude=gps_longitude,
                gps_sats=gps_sats,
                cmd_echo=cmd_echo,
                optional_data=optional_data,
            )
        except (ValueError, IndexError) as err:
            logger.warning("Error parsing CanSat CSV values: %s | Line: %s", err, line)
            return None


# ============================================================
# LEGACY 65-BYTE BINARY PROTOCOL SUPPORT
# ============================================================

@dataclass
class FieldConfig:
    name: str
    type: str
    scale: float = 1.0
    value_offset: float = 0.0
    byte_offset: Optional[int] = None
    byte_length: Optional[int] = None
    values: dict[int, str] = field(default_factory=dict)
    expected_value: Optional[int] = None

@dataclass
class FrameConfig:
    endian: str
    fields: list[FieldConfig]
    sequence_field: Optional[str] = None
    sync: bytes = b""
    crc_type: Optional[str] = None
    crc_size: int = 0
    frame_length: Optional[int] = None
    crc_offset: Optional[int] = None
    crc_endian: Optional[str] = None
    crc_calculate_from: Optional[int] = None
    crc_calculate_to: Optional[int] = None
    crc_polynomial: int = 0x1021
    crc_initial_value: int = 0xFFFF
    crc_final_xor: int = 0

    @property
    def payload_size(self) -> int:
        return sum(field_size(f) for f in self.fields)

    @property
    def frame_size(self) -> int:
        if self.frame_length is not None:
            return self.frame_length
        return len(self.sync) + self.payload_size + self.crc_size


TYPE_FORMATS: dict[str, tuple[str, int]] = {
    "uint8": ("B", 1),
    "int8": ("b", 1),
    "uint16": ("H", 2),
    "int16": ("h", 2),
    "uint24": ("", 3),
    "int24": ("", 3),
    "uint32": ("I", 4),
    "int32": ("i", 4),
    "uint64": ("Q", 8),
    "int64": ("q", 8),
    "float32": ("f", 4),
    "float64": ("d", 8),
    "bool": ("?", 1),
    "bytes": ("", 0),
}

def field_size(field_config: FieldConfig) -> int:
    if field_config.type == "bytes":
        return field_config.byte_length or 0
    return TYPE_FORMATS[field_config.type][1]

def crc16_ccitt(
    data: bytes,
    polynomial: int = 0x1021,
    initial_value: int = 0xFFFF,
    final_xor: int = 0,
) -> int:
    crc = initial_value
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ polynomial) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc ^ final_xor

def validate_crc(
    data: bytes,
    crc_bytes: bytes,
    crc_type: Optional[str],
    endian: str,
    polynomial: int = 0x1021,
    initial_value: int = 0xFFFF,
    final_xor: int = 0,
) -> bool:
    if not crc_type:
        return True
    crc_algorithm = (
        crc_type.upper().replace("-", "").replace("_", "").replace("/", "")
        if crc_type else None
    )
    if crc_algorithm in ("CRC16CCITT", "CRC16CCITTFALSE"):
        if len(crc_bytes) != 2:
            return False
        calculated = crc16_ccitt(data, polynomial, initial_value, final_xor)
        received = int.from_bytes(crc_bytes, byteorder=endian)
        return calculated == received
    return True

class FrameParser:
    def __init__(self, config: FrameConfig):
        self.config = config
        self.struct_prefix = "<" if config.endian == "little" else ">"

    def parse(self, frame: bytes) -> Optional[dict[str, Any]]:
        expected_size = self.config.frame_size
        if len(frame) != expected_size:
            return None
        if self.config.sync and not frame.startswith(self.config.sync):
            return None

        if self.config.crc_type and self.config.crc_size:
            crc_offset = (
                self.config.crc_offset
                if self.config.crc_offset is not None
                else len(frame) - self.config.crc_size
            )
            crc_bytes = frame[crc_offset : crc_offset + self.config.crc_size]
            calc_from = self.config.crc_calculate_from or 0
            calc_to = self.config.crc_calculate_to or (crc_offset - 1)
            crc_data = frame[calc_from : calc_to + 1]
            if not validate_crc(
                crc_data,
                crc_bytes,
                self.config.crc_type,
                self.config.crc_endian or self.config.endian,
                self.config.crc_polynomial,
                self.config.crc_initial_value,
                self.config.crc_final_xor,
            ):
                return None

        res: dict[str, Any] = {}
        payload_offset = len(self.config.sync)
        for fc in self.config.fields:
            struct_fmt, sz = TYPE_FORMATS[fc.type]
            off = fc.byte_offset if fc.byte_offset is not None else payload_offset
            if off + sz > len(frame):
                return None
            val = struct.unpack_from(self.struct_prefix + struct_fmt, frame, off)[0]
            val = val * fc.scale + fc.value_offset
            res[fc.name] = val
            if fc.values:
                res[f"{fc.name}_label"] = fc.values.get(int(val))
            if fc.byte_offset is None:
                payload_offset += sz
        return res

class FrameBuffer:
    def __init__(self, parser: FrameParser):
        self.parser = parser
        self.buffer = bytearray()
        self.invalid_frames = 0
        self.last_raw_frames: list[bytes] = []
        self.resyncing = False

    def feed(self, data: bytes) -> list[dict[str, Any]]:
        self.buffer.extend(data)
        frames: list[dict[str, Any]] = []
        self.last_raw_frames = []
        fsz = self.parser.config.frame_size

        while len(self.buffer) >= fsz:
            if self.parser.config.sync:
                idx = self.buffer.find(self.parser.config.sync)
                if idx == -1:
                    self.buffer = self.buffer[-max(0, len(self.parser.config.sync) - 1):]
                    break
                if idx > 0:
                    del self.buffer[:idx]
                    if len(self.buffer) < fsz:
                        break

            candidate = bytes(self.buffer[:fsz])
            parsed = self.parser.parse(candidate)
            if parsed is not None:
                del self.buffer[:fsz]
                frames.append(parsed)
                self.last_raw_frames.append(candidate)
                self.resyncing = False
            else:
                if not self.resyncing:
                    self.invalid_frames += 1
                del self.buffer[:1]
                self.resyncing = True

        return frames


# ============================================================
# CONFIG DATA STRUCTURES & LOADERS
# ============================================================

@dataclass
class SerialConfig:
    port: str
    baudrate: int
    reconnect_delay: float

@dataclass
class WebSocketConfig:
    host: str
    port: int

@dataclass
class StorageConfig:
    database: str
    primary_csv: str
    backup_csv: str

@dataclass
class MissionLimitsConfig:
    altitude_max_m: float = 1000.0
    descent_c3_nominal_ms: float = 15.0
    descent_c3_tol_ms: float = 3.0
    descent_c4_nominal_ms: float = 5.0
    descent_c4_tol_ms: float = 3.0
    voltage_min_v: float = 3.3
    voltage_nominal_v: float = 3.7
    voltage_max_v: float = 4.2
    current_max_a: float = 1.0

@dataclass
class AppConfig:
    team_id: str
    mode: str
    serial: SerialConfig
    websocket: WebSocketConfig
    storage: StorageConfig
    mission_limits: MissionLimitsConfig = field(default_factory=MissionLimitsConfig)

def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}

def load_app_config() -> AppConfig:
    data = load_yaml(APP_CONFIG_FILE)
    team_data = data.get("team", {})
    serial_data = data.get("serial", {})
    ws_data = data.get("websocket", {})
    storage_data = data.get("storage", {})
    limits_data = data.get("mission_limits", {})

    team_id = str(team_data.get("id", "1000"))
    mode = str(team_data.get("mode", "F"))

    # Determine CSV paths, ensuring Flight_XXXX.csv naming format (G2)
    primary_csv = storage_data.get("primary_csv", str(DATA_DIR / f"Flight_{team_id}.csv"))
    backup_csv = storage_data.get("backup_csv", str(BACKUP_DIR / f"Flight_{team_id}.csv"))

    return AppConfig(
        team_id=team_id,
        mode=mode,
        serial=SerialConfig(
            port=str(serial_data.get("port", "/dev/ttyACM0")),
            baudrate=int(serial_data.get("baudrate", 115200)),
            reconnect_delay=float(serial_data.get("reconnect_delay", 2.0)),
        ),
        websocket=WebSocketConfig(
            host=str(ws_data.get("host", "0.0.0.0")),
            port=int(ws_data.get("port", 8000)),
        ),
        storage=StorageConfig(
            database=str(storage_data.get("database", str(DATA_DIR / "telemetry.db"))),
            primary_csv=primary_csv,
            backup_csv=backup_csv,
        ),
        mission_limits=MissionLimitsConfig(
            altitude_max_m=float(limits_data.get("altitude_max_m", 1000.0)),
            descent_c3_nominal_ms=float(limits_data.get("descent_c3_nominal_ms", 15.0)),
            descent_c3_tol_ms=float(limits_data.get("descent_c3_tol_ms", 3.0)),
            descent_c4_nominal_ms=float(limits_data.get("descent_c4_nominal_ms", 5.0)),
            descent_c4_tol_ms=float(limits_data.get("descent_c4_tol_ms", 3.0)),
            voltage_min_v=float(limits_data.get("voltage_min_v", 3.3)),
            voltage_nominal_v=float(limits_data.get("voltage_nominal_v", 3.7)),
            voltage_max_v=float(limits_data.get("voltage_max_v", 4.2)),
            current_max_a=float(limits_data.get("current_max_a", 1.0)),
        ),
    )


def parse_hex_bytes(value: Any) -> bytes:
    if value is None:
        return b""
    if isinstance(value, list):
        return bytes(value)
    if isinstance(value, str):
        val = value.strip().replace(" ", "").replace("0x", "")
        return bytes.fromhex(val) if val else b""
    raise ValueError("The sync field must be a list of bytes or a hexadecimal string.")


def load_frame_config(path: Optional[Path] = None) -> FrameConfig:
    target_path = Path(path) if path else (CONFIG_DIR / "frame_65b.yaml" if (CONFIG_DIR / "frame_65b.yaml").exists() else FRAME_CONFIG_FILE)
    data = load_yaml(target_path)
    protocol_data = data.get("protocol", {})
    frame_data = data.get("frame", {})

    endian_val = str(frame_data.get("byte_order", protocol_data.get("endian", "little"))).lower()
    endian = {"little_endian": "little", "big_endian": "big"}.get(endian_val, endian_val)

    fields_data = data.get("fields", frame_data.get("fields", []))
    fields: list[FieldConfig] = []
    for item in fields_data:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        ftype = item.get("type", "uint8")
        if ftype not in TYPE_FORMATS:
            continue
        decl_len = item.get("length")
        byte_off = int(item["offset"]) if item.get("offset") is not None else None
        val_off = item.get("offset_value", 0.0)
        values = item.get("values", {})
        fields.append(
            FieldConfig(
                name=str(name),
                type=str(ftype),
                scale=float(item.get("scale", 1.0)),
                value_offset=float(val_off),
                byte_offset=byte_off,
                byte_length=int(decl_len) if decl_len is not None else None,
                values={int(v): str(lbl) for v, lbl in values.items()} if isinstance(values, dict) else {},
                expected_value=int(item["expected_value"]) if "expected_value" in item else None,
            )
        )

    sync = parse_hex_bytes(frame_data.get("sync"))
    crc_data = frame_data.get("crc", {})
    crc_enabled = crc_data.get("enabled", True) if isinstance(crc_data, dict) else False
    crc_type = crc_data.get("algorithm", crc_data.get("type")) if crc_enabled else None
    crc_size = int(crc_data.get("length", crc_data.get("size", 0))) if crc_enabled else 0
    crc_offset = int(crc_data["offset"]) if isinstance(crc_data, dict) and crc_data.get("offset") is not None else None

    crc_endian_val = str(crc_data.get("byte_order", endian)).lower() if isinstance(crc_data, dict) else endian
    crc_endian = {"little_endian": "little", "big_endian": "big"}.get(crc_endian_val, crc_endian_val)

    frame_len = int(frame_data.get("length", 65)) if frame_data.get("length") is not None else None

    return FrameConfig(
        endian=endian,
        fields=fields,
        sequence_field=frame_data.get("sequence_field", "frame_number"),
        sync=sync,
        crc_type=crc_type,
        crc_size=crc_size,
        frame_length=frame_len,
        crc_offset=crc_offset,
        crc_endian=crc_endian,
        crc_calculate_from=int(crc_data["calculate_from"]) if isinstance(crc_data, dict) and "calculate_from" in crc_data else None,
        crc_calculate_to=int(crc_data["calculate_to"]) if isinstance(crc_data, dict) and "calculate_to" in crc_data else None,
        crc_polynomial=int(crc_data.get("polynomial", 0x1021)) if isinstance(crc_data, dict) else 0x1021,
        crc_initial_value=int(crc_data.get("initial_value", 0xFFFF)) if isinstance(crc_data, dict) else 0xFFFF,
        crc_final_xor=int(crc_data.get("final_xor", 0)) if isinstance(crc_data, dict) else 0,
    )


# ============================================================
# PACKET STATISTICS & LINK HEALTH TRACKER (G14, G8)
# ============================================================

class PacketStatistics:
    """Quantitative link tracking for CanSat telemetry.

    - G14: rx_count counts packets received with success.
    - G8: lost counts missing sequences based on persistent PACKET_COUNT.
    - C3 / C4: computes descent velocity Vz and verifies speed bounds.
    """

    def __init__(self, sequence_field: Optional[str] = None):
        self.sequence_field = sequence_field
        self.received = 0        # RX Count (G14)
        self.lost = 0            # Lost Packets Count (G8)
        self.invalid = 0         # CRC/format errors
        self.last_packet_count: Optional[int] = None
        self.packet_timestamps = deque(maxlen=20)
        self.last_altitude: Optional[float] = None
        self.last_alt_time: Optional[float] = None
        self.vertical_velocity: float = 0.0

    def register(self, packet_count: Any = None, altitude: Optional[float] = None, packet_or_frame: Any = None):
        now = time.time()
        self.received += 1
        self.packet_timestamps.append(now)

        item = packet_count if packet_count is not None else packet_or_frame
        seq = None
        alt = altitude

        if isinstance(item, dict):
            frame = item
            if self.sequence_field and self.sequence_field in frame:
                seq = frame[self.sequence_field]
            elif "PACKET_COUNT" in frame:
                seq = frame["PACKET_COUNT"]
            elif "frame_number" in frame:
                seq = frame["frame_number"]
            if alt is None:
                alt = frame.get("ALTITUDE", frame.get("altura_actual"))
        else:
            seq = item

        # Track packet loss using persistent CanSat PACKET_COUNT
        if seq is not None:
            try:
                seq_int = int(seq)
                if self.last_packet_count is not None:
                    expected = self.last_packet_count + 1
                    if seq_int > expected:
                        self.lost += (seq_int - expected)
                self.last_packet_count = seq_int
            except (ValueError, TypeError):
                pass

        # Compute vertical velocity Vz (m/s)
        if alt is not None:
            try:
                alt_flt = float(alt)
                if self.last_altitude is not None and self.last_alt_time is not None:
                    dt = now - self.last_alt_time
                    if dt >= 0.5:
                        self.vertical_velocity = round((alt_flt - self.last_altitude) / dt, 2)
                        self.last_altitude = alt_flt
                        self.last_alt_time = now
                else:
                    self.last_altitude = alt_flt
                    self.last_alt_time = now
            except (ValueError, TypeError):
                pass

    def snapshot(self) -> dict[str, Any]:
        total = self.received + self.lost
        loss_pct = (self.lost / total * 100.0) if total > 0 else 0.0

        # Compute rolling rate in Hz
        rate_hz = 0.0
        if len(self.packet_timestamps) >= 2:
            duration = self.packet_timestamps[-1] - self.packet_timestamps[0]
            if duration > 0.0:
                rate_hz = round((len(self.packet_timestamps) - 1) / duration, 2)

        return {
            "received": self.received,
            "rx_count": self.received,
            "frames_received": self.received,
            "lost": self.lost,
            "lost_count": self.lost,
            "invalid": self.invalid,
            "loss_percent": round(loss_pct, 1),
            "rate_hz": rate_hz,
            "vertical_velocity": self.vertical_velocity,
        }


# ============================================================
# CSV LOGGERS (G2: NOTEBOOK + BACKUP STORAGE FLUSH)
# ============================================================

class CSVLogger:
    def __init__(self, path: str, fields: list[str]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fields = fields
        self.file = self.path.open("a", newline="", encoding="utf-8")
        self.writer = csv.DictWriter(self.file, fieldnames=["timestamp", *self.fields])
        if self.path.stat().st_size == 0:
            self.writer.writeheader()
            self.file.flush()

    def write(self, data: dict[str, Any]):
        row = {"timestamp": time.time(), **{f: data.get(f) for f in self.fields}}
        self.writer.writerow(row)
        self.file.flush()

    def close(self):
        try:
            self.file.close()
        except Exception:
            pass


class DualCSVLogger:
    """Simultaneously logs telemetry to primary and backup disks with immediate flush (G2)."""

    def __init__(self, primary_path: str, backup_path: str):
        self.primary_path = Path(primary_path)
        self.backup_path = Path(backup_path)

        self.primary_path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_path.parent.mkdir(parents=True, exist_ok=True)

        self.header = ",".join(CANSAT_FIELDS) + "\n"

        self._init_file(self.primary_path)
        self._init_file(self.backup_path)

        self.primary_file = self.primary_path.open("a", newline="", encoding="utf-8")
        self.backup_file = self.backup_path.open("a", newline="", encoding="utf-8")

        logger.info("Primary CSV active: %s", self.primary_path)
        logger.info("Backup CSV active: %s", self.backup_path)

    def _init_file(self, path: Path):
        if not path.exists() or path.stat().st_size == 0:
            with path.open("w", newline="", encoding="utf-8") as f:
                f.write(self.header)
                f.flush()

    def write_telemetry(self, telemetry: CanSatTelemetry):
        row = telemetry.to_csv_row() + "\n"
        try:
            self.primary_file.write(row)
            self.primary_file.flush()
            os.fsync(self.primary_file.fileno())
        except Exception:
            logger.exception("Error writing primary CSV")

        try:
            self.backup_file.write(row)
            self.backup_file.flush()
            os.fsync(self.backup_file.fileno())
        except Exception:
            logger.exception("Error writing backup CSV")

    def close(self):
        try:
            self.primary_file.close()
        except Exception:
            pass
        try:
            self.backup_file.close()
        except Exception:
            pass


# ============================================================
# SQLITE DATABASE PERSISTENCE
# ============================================================

class Database:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                sequence INTEGER,
                packet_count INTEGER,
                team_id TEXT,
                state TEXT,
                payload TEXT NOT NULL
            )
            """
        )
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry(timestamp)")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS commands_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                iso_time TEXT NOT NULL,
                command TEXT NOT NULL,
                status TEXT NOT NULL,
                echo TEXT
            )
            """
        )
        self.connection.commit()

    def insert(
        self,
        packet_count: Any = None,
        sequence_field: Optional[str] = None,
        team_id: str = "1000",
        state: str = "UNKNOWN",
        data: Optional[dict[str, Any]] = None,
        packet_count_or_data: Any = None,
    ):
        target = packet_count if packet_count is not None else packet_count_or_data
        if isinstance(target, dict):
            payload_data = target
            seq = None
            if sequence_field and sequence_field in payload_data:
                seq = payload_data[sequence_field]
            elif "PACKET_COUNT" in payload_data:
                seq = payload_data["PACKET_COUNT"]
            elif "frame_number" in payload_data:
                seq = payload_data["frame_number"]
            team = payload_data.get("TEAM_ID", team_id)
            st = payload_data.get("STATE", payload_data.get("status", state))
        else:
            seq = target
            team = team_id
            st = state
            payload_data = data or {}

        self.connection.execute(
            """
            INSERT INTO telemetry (timestamp, sequence, packet_count, team_id, state, payload)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (time.time(), seq, seq, str(team), str(st), json.dumps(payload_data, ensure_ascii=False)),
        )
        self.connection.commit()

    def log_command(self, command: str, status: str = "SENT", echo: Optional[str] = None):
        ts = time.time()
        iso = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()
        self.connection.execute(
            """
            INSERT INTO commands_log (timestamp, iso_time, command, status, echo)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ts, iso, command, status, echo),
        )
        self.connection.commit()

    def get_recent(self, seconds: float = 60.0, limit: int = 1200) -> list[dict[str, Any]]:
        try:
            cursor = self.connection.cursor()
            min_ts = time.time() - max(1.0, seconds)
            cursor.execute(
                """
                SELECT timestamp, packet_count, payload
                FROM telemetry
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (min_ts, limit),
            )
            rows = cursor.fetchall()
            results = []
            for ts, seq, payload in rows:
                try:
                    payload_data = json.loads(payload)
                    results.append({
                        "timestamp": ts,
                        "sequence": seq,
                        "data": payload_data,
                    })
                except Exception:
                    continue
            return results
        except Exception:
            logger.exception("Error querying SQLite telemetry history")
            return []

    def close(self):
        try:
            self.connection.close()
        except Exception:
            pass


# ============================================================
# WEBSOCKET MANAGER
# ============================================================

class WebSocketManager:
    def __init__(self):
        self.clients: set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            self.clients.add(websocket)
        logger.info("WebSocket connected | clients=%d", len(self.clients))

    async def disconnect(self, websocket: WebSocket):
        async with self.lock:
            self.clients.discard(websocket)
        logger.info("WebSocket disconnected | clients=%d", len(self.clients))

    async def broadcast(self, message: dict[str, Any]):
        if not self.clients:
            return
        dead = []
        async with self.lock:
            current_clients = list(self.clients)

        for ws in current_clients:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        if dead:
            async with self.lock:
                for ws in dead:
                    self.clients.discard(ws)


# ============================================================
# RUNTIME STATE & GLOBAL INSTANCES
# ============================================================

@dataclass
class RuntimeState:
    connected: bool = False
    last_frame: Optional[dict[str, Any]] = None
    last_raw_line: str = ""
    last_timestamp: Optional[float] = None
    frames_received: int = 0
    history: deque = field(default_factory=lambda: deque(maxlen=3600))
    last_sent_command: Optional[str] = None
    command_in_flight: bool = False

app_config: Optional[AppConfig] = None
statistics = PacketStatistics()
database: Optional[Database] = None
dual_csv_logger: Optional[DualCSVLogger] = None
websocket_manager = WebSocketManager()
runtime = RuntimeState()
serial_transport: Optional[asyncio.Transport] = None
background_tasks: set[asyncio.Task] = set()

def create_background_task(coroutine) -> asyncio.Task:
    task = asyncio.create_task(coroutine)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return task


# ============================================================
# TELEMETRY DISPATCH PIPELINE
# ============================================================

async def process_telemetry(telemetry: CanSatTelemetry, raw_line: str):
    data_dict = telemetry.to_dict()
    statistics.register(telemetry.packet_count, telemetry.altitude)

    # Persist simultaneously to Dual CSV (G2) and SQLite
    if dual_csv_logger is not None:
        dual_csv_logger.write_telemetry(telemetry)

    if database is not None:
        database.insert(
            packet_count=telemetry.packet_count,
            team_id=telemetry.team_id,
            state=telemetry.state,
            data=data_dict,
        )

    runtime.last_frame = data_dict
    runtime.last_raw_line = raw_line
    runtime.last_timestamp = time.time()
    runtime.frames_received = statistics.received

    snapshot = statistics.snapshot()

    history_item = {
        "timestamp": runtime.last_timestamp,
        "sequence": telemetry.packet_count,
        "data": data_dict,
        "raw_line": raw_line,
        "statistics": snapshot,
    }
    runtime.history.append(history_item)

    # Broadcast to connected GUI dashboards (G5: raw text + decoded SI telemetry)
    await websocket_manager.broadcast({
        "type": "telemetry",
        "timestamp": runtime.last_timestamp,
        "raw_line": raw_line,
        "data": data_dict,
        "statistics": snapshot,
    })


# ============================================================
# SERIAL PROTOCOL & TELECOMMAND DISPATCH (G15, G1)
# ============================================================

class CanSatSerialProtocol(asyncio.Protocol):
    def __init__(self, loop):
        self.loop = loop
        self.transport = None
        self.disconnected = asyncio.Event()
        self.line_buffer = bytearray()

    def connection_made(self, transport):
        global serial_transport
        self.transport = transport
        serial_transport = transport
        runtime.connected = True
        logger.info("Serial interface connected to CanSat transceiver")
        create_background_task(websocket_manager.broadcast({"type": "connection", "connected": True}))

    def data_received(self, data: bytes):
        if not data:
            return

        self.line_buffer.extend(data)

        # Split on newline characters (\n or \r\n)
        while b"\n" in self.line_buffer:
            idx = self.line_buffer.find(b"\n")
            raw_bytes = bytes(self.line_buffer[:idx])
            del self.line_buffer[:idx + 1]

            line_str = raw_bytes.decode("utf-8", errors="replace").strip("\r")
            if not line_str:
                continue

            parsed = CanSatAsciiParser.parse_line(line_str)
            if parsed is not None:
                create_background_task(process_telemetry(parsed, line_str))
            else:
                statistics.invalid += 1
                logger.warning("Unparseable telemetry line received: %s", line_str)

    def connection_lost(self, exc):
        global serial_transport
        serial_transport = None
        runtime.connected = False
        if exc:
            logger.error("Serial connection lost: %s", exc)
        else:
            logger.info("Serial port closed normally")
        self.disconnected.set()
        create_background_task(websocket_manager.broadcast({"type": "connection", "connected": False}))


async def send_telecommand(command_str: str) -> dict[str, Any]:
    """Transmits a telecommand over the serial radio interface to the CanSat (G15, G1)."""
    clean_cmd = command_str.strip()
    if not clean_cmd:
        raise ValueError("Command cannot be empty")

    cmd_payload = (clean_cmd + "\r\n").encode("utf-8")
    status = "SENT"

    if serial_transport is not None and not serial_transport.is_closing():
        try:
            serial_transport.write(cmd_payload)
            logger.info("Telecommand sent to CanSat: %s", clean_cmd)
        except Exception as e:
            logger.exception("Error transmitting telecommand over UART")
            status = f"ERROR: {e}"
    else:
        logger.warning("Serial link not connected. Simulating command dispatch: %s", clean_cmd)
        status = "QUEUED_OFFLINE"

    runtime.last_sent_command = clean_cmd
    if database is not None:
        database.log_command(clean_cmd, status=status)

    # Broadcast command event to GUI clients
    await websocket_manager.broadcast({
        "type": "command_dispatched",
        "command": clean_cmd,
        "status": status,
        "timestamp": time.time(),
    })

    return {"status": status, "command": clean_cmd, "timestamp": time.time()}


async def serial_loop():
    while True:
        if app_config is None:
            await asyncio.sleep(1)
            continue

        transport = None
        try:
            logger.info(
                "Connecting to CanSat radio on %s @ %d baud",
                app_config.serial.port,
                app_config.serial.baudrate,
            )
            loop = asyncio.get_running_loop()
            transport, protocol = await serial_asyncio.create_serial_connection(
                loop,
                lambda: CanSatSerialProtocol(loop),
                app_config.serial.port,
                baudrate=app_config.serial.baudrate,
            )
            await protocol.disconnected.wait()
        except asyncio.CancelledError:
            logger.info("Serial loop cancelled")
            if transport is not None:
                transport.close()
            raise
        except Exception:
            runtime.connected = False
            logger.exception("CanSat serial connection error")
        finally:
            runtime.connected = False
            if transport is not None:
                try:
                    transport.close()
                except Exception:
                    pass

        await asyncio.sleep(app_config.serial.reconnect_delay)


# ============================================================
# FASTAPI APPLICATION & REST ENDPOINTS
# ============================================================

app = FastAPI(
    title="CanSat CONAE Ground Station",
    description="Official ground station application for CanSat CONAE 2026-2027",
    version="2.0.0",
)

app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")
if (FRONTEND_DIR / "css").exists():
    app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
if (FRONTEND_DIR / "js").exists():
    app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")
if (FRONTEND_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")


@app.get("/")
@app.get("/index.html")
async def root():
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse({"error": "Dashboard frontend not found", "path": str(index_file)}, status_code=404)
    return FileResponse(index_file)


@app.get("/api/status")
async def status():
    """Ground station health, storage status, and quantitative link metrics."""
    du = shutil.disk_usage(str(DATA_DIR))
    team_id = app_config.team_id if app_config else "1000"
    primary_csv_path = Path(app_config.storage.primary_csv) if app_config else (DATA_DIR / f"Flight_{team_id}.csv")
    backup_csv_path = Path(app_config.storage.backup_csv) if app_config else (BACKUP_DIR / f"Flight_{team_id}.csv")

    return {
        "connected": runtime.connected,
        "team_id": team_id,
        "mode": app_config.mode if app_config else "F",
        "frames_received": runtime.frames_received,
        "last_timestamp": runtime.last_timestamp,
        "last_raw_line": runtime.last_raw_line,
        "statistics": statistics.snapshot(),
        "storage": {
            "primary_csv": str(primary_csv_path),
            "primary_exists": primary_csv_path.exists(),
            "primary_size_bytes": primary_csv_path.stat().st_size if primary_csv_path.exists() else 0,
            "backup_csv": str(backup_csv_path),
            "backup_exists": backup_csv_path.exists(),
            "backup_size_bytes": backup_csv_path.stat().st_size if backup_csv_path.exists() else 0,
            "disk_free_mb": round(du.free / (1024 * 1024), 1),
            "disk_free_pct": round(du.free / du.total * 100, 1),
        },
        "last_sent_command": runtime.last_sent_command,
        "server_time": datetime.datetime.now().strftime("%H:%M:%S"),
    }


@app.get("/api/telemetry")
async def get_latest_telemetry():
    """Return the latest parsed telemetry packet."""
    return {
        "connected": runtime.connected,
        "timestamp": runtime.last_timestamp,
        "data": runtime.last_frame,
        "raw_line": runtime.last_raw_line,
        "statistics": statistics.snapshot(),
    }


@app.get("/api/history")
async def get_history(seconds: float = 60.0, limit: int = 1200):
    """Return recent telemetry history for dashboard chart hydration."""
    now = time.time()
    min_ts = now - max(1.0, seconds)

    in_memory = [
        item for item in runtime.history
        if item.get("timestamp") and item["timestamp"] >= min_ts
    ]

    if len(in_memory) >= 5:
        if len(in_memory) > limit:
            in_memory = in_memory[-limit:]
        return {
            "count": len(in_memory),
            "seconds": seconds,
            "frames": in_memory,
            "statistics": statistics.snapshot(),
        }

    # Fallback to SQLite
    if database is not None:
        db_frames = database.get_recent(seconds=seconds, limit=limit)
        return {
            "count": len(db_frames),
            "seconds": seconds,
            "frames": db_frames,
            "statistics": statistics.snapshot(),
        }

    return {"count": len(in_memory), "seconds": seconds, "frames": in_memory, "statistics": statistics.snapshot()}


@app.post("/api/command")
async def post_command(request: Request):
    """Receive and dispatch a telecommand from the GUI to the CanSat (G15, G1)."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    cmd = body.get("command")
    if not cmd:
        action = body.get("action")
        team_id = app_config.team_id if app_config else "1000"
        if action == "calibrate_zero":
            cmd = f"CMD,{team_id},CAL"
        elif action == "set_time":
            utc_now = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
            cmd = f"CMD,{team_id},ST,{utc_now}"
        elif action == "reset_packet_count":
            cmd = f"CMD,{team_id},PC,0"
        elif action == "request_battery_solar":
            cmd = f"CMD,{team_id},BATT"
        elif action == "sim_enable":
            cmd = f"CMD,{team_id},SIM,ENABLE"
        elif action == "sim_activate":
            cmd = f"CMD,{team_id},SIM,ACTIVATE"
        elif action == "sim_disable":
            cmd = f"CMD,{team_id},SIM,DISABLE"
        elif action == "mission_start":
            cmd = f"CMD,{team_id},START"
        else:
            raise HTTPException(status_code=400, detail="Missing 'command' or recognized 'action'")

    try:
        result = await send_telecommand(cmd)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/export/csv")
async def export_csv(target: str = "primary"):
    """Export the Flight_XXXX.csv file for immediate USB handover to judges."""
    if app_config is None:
        raise HTTPException(status_code=500, detail="Configuration not loaded")

    csv_path = Path(app_config.storage.primary_csv if target == "primary" else app_config.storage.backup_csv)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV file not found at {csv_path}")

    return FileResponse(
        csv_path,
        media_type="text/csv",
        filename=csv_path.name,
    )


@app.websocket("/ws/telemetry")
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Live bidirectional WebSocket for telemetry streaming and command status."""
    await websocket_manager.connect(websocket)
    try:
        await websocket.send_json({"type": "connection", "connected": runtime.connected})

        if runtime.last_frame is not None:
            await websocket.send_json({
                "type": "telemetry",
                "timestamp": runtime.last_timestamp,
                "raw_line": runtime.last_raw_line,
                "data": runtime.last_frame,
                "statistics": statistics.snapshot(),
            })

        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
                if data.get("type") == "command" and "command" in data:
                    await send_telecommand(data["command"])
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket communication error")
    finally:
        await websocket_manager.disconnect(websocket)


# ============================================================
# APPLICATION LIFECYCLE (STARTUP & SHUTDOWN)
# ============================================================

@app.on_event("startup")
async def startup():
    global app_config, database, dual_csv_logger

    logger.info("Initializing CanSat CONAE Ground Station...")
    app_config = load_app_config()

    database = Database(app_config.storage.database)
    dual_csv_logger = DualCSVLogger(
        primary_path=app_config.storage.primary_csv,
        backup_path=app_config.storage.backup_csv,
    )

    create_background_task(serial_loop())
    logger.info("Ground Station running | Team: %s | Mode: %s", app_config.team_id, app_config.mode)


@app.on_event("shutdown")
async def shutdown():
    runtime.connected = False
    logger.info("Shutting down CanSat Ground Station...")

    current_task = asyncio.current_task()
    tasks_to_cancel = [t for t in background_tasks if t is not current_task]
    for t in tasks_to_cancel:
        t.cancel()

    if tasks_to_cancel:
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

    if database is not None:
        database.close()

    if dual_csv_logger is not None:
        dual_csv_logger.close()

    logger.info("Ground Station shutdown complete")


# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    conf = load_app_config()
    uvicorn.run(
        app,
        host=conf.websocket.host,
        port=conf.websocket.port,
        log_level="info",
    )
