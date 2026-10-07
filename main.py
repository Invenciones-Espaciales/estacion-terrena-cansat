# main.py

import asyncio
import csv
import json
import logging
import sqlite3
import struct
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import serial_asyncio
import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import uvicorn
from fastapi.responses import FileResponse


# ============================================================
# WINDOWS / ASYNCIO
# ============================================================

# pyserial-asyncio trabaja de forma más estable con SelectorEventLoop
# en Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"

APP_CONFIG_FILE = CONFIG_DIR / "app.yaml"
FRAME_CONFIG_FILE = CONFIG_DIR / "frame.yaml"

DATA_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("telemetry")


# ============================================================
# CONFIGURATION
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
        return sum(field_size(field) for field in self.fields)

    @property
    def frame_size(self) -> int:
        if self.frame_length is not None:
            return self.frame_length

        if all(field_config.byte_offset is not None for field_config in self.fields):
            field_end = max(
                field_config.byte_offset + field_size(field_config)
                for field_config in self.fields
            )
            crc_end = (
                self.crc_offset + self.crc_size
                if self.crc_offset is not None
                else 0
            )
            return max(field_end, crc_end, len(self.sync))

        return (
            len(self.sync)
            + self.payload_size
            + self.crc_size
        )


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
    csv: str


@dataclass
class AppConfig:
    serial: SerialConfig
    websocket: WebSocketConfig
    storage: StorageConfig


# ============================================================
# BINARY TYPES
# ============================================================

# type -> (struct format, size)
TYPE_FORMATS = {
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


# ============================================================
# CONFIG LOADING
# ============================================================

def load_yaml(path: Path) -> dict[str, Any]:

    if not path.exists():
        raise FileNotFoundError(
            f"No existe el archivo de configuración: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError(
            f"Configuración inválida: {path}"
        )

    return data


def parse_hex_bytes(value: Any) -> bytes:

    if value is None:
        return b""

    if isinstance(value, list):
        return bytes(value)

    if isinstance(value, str):

        value = value.strip()

        if not value:
            return b""

        value = value.replace(" ", "").replace("0x", "")

        return bytes.fromhex(value)

    raise ValueError(
        "El campo sync debe ser una lista de bytes "
        "o una cadena hexadecimal."
    )


def load_app_config() -> AppConfig:

    data = load_yaml(APP_CONFIG_FILE)

    serial_data = data.get("serial", {})
    websocket_data = data.get("websocket", {})
    storage_data = data.get("storage", {})

    serial_config = SerialConfig(
        port=str(
            serial_data.get(
                "port",
                "COM6",
            )
        ),
        baudrate=int(
            serial_data.get(
                "baudrate",
                115200,
            )
        ),
        reconnect_delay=float(
            serial_data.get(
                "reconnect_delay",
                3,
            )
        ),
    )

    websocket_config = WebSocketConfig(
        host=str(
            websocket_data.get(
                "host",
                "0.0.0.0",
            )
        ),
        port=int(
            websocket_data.get(
                "port",
                8000,
            )
        ),
    )

    storage_config = StorageConfig(
        database=str(
            storage_data.get(
                "database",
                str(DATA_DIR / "telemetry.db"),
            )
        ),
        csv=str(
            storage_data.get(
                "csv",
                str(DATA_DIR / "telemetry.csv"),
            )
        ),
    )

    return AppConfig(
        serial=serial_config,
        websocket=websocket_config,
        storage=storage_config,
    )


def load_frame_config() -> FrameConfig:

    data = load_yaml(FRAME_CONFIG_FILE)

    protocol_data = data.get(
        "protocol",
        {},
    )

    frame_data = data.get(
        "frame",
        {},
    )

    endian_value = frame_data.get(
        "byte_order",
        protocol_data.get("endian", "little"),
    )
    endian_value = str(endian_value).lower()
    endian = {
        "little_endian": "little",
        "big_endian": "big",
    }.get(endian_value, endian_value)

    if endian not in ("little", "big"):
        raise ValueError(
            "El byte order debe ser 'little' o 'big' "
            "(también se acepta little_endian/big_endian)."
        )

    fields_data = data.get(
        "fields",
        frame_data.get("fields", []),
    )

    if not fields_data:
        raise ValueError("No hay campos definidos en fields.")

    fields = []

    for item in fields_data:

        if not isinstance(item, dict):
            raise ValueError(
                "Cada campo de frame.fields debe ser un objeto."
            )

        name = item.get("name")
        field_type = item.get("type")

        if not name:
            raise ValueError(
                "Existe un campo sin 'name'."
            )

        if field_type not in TYPE_FORMATS:
            raise ValueError(
                f"Tipo desconocido '{field_type}' "
                f"para el campo '{name}'."
            )

        declared_length = item.get("length")
        if field_type == "bytes" and declared_length is None:
            raise ValueError(
                f"El campo '{name}' de tipo bytes necesita declarar length."
            )
        if field_type != "bytes" and (
            declared_length is not None
            and int(declared_length) != TYPE_FORMATS[field_type][1]
        ):
            raise ValueError(
                f"El campo '{name}' declara {declared_length} bytes, "
                f"pero el tipo '{field_type}' requiere "
                f"{TYPE_FORMATS[field_type][1]}."
            )
        if field_type == "bytes" and int(declared_length) <= 0:
            raise ValueError(
                f"El campo '{name}' debe tener length mayor que cero."
            )

        byte_offset = item.get("offset")
        byte_offset = (
            int(byte_offset)
            if byte_offset is not None
            else None
        )
        value_offset = item.get(
            "offset_value",
            item.get("offset", 0.0)
            if byte_offset is None
            else 0.0,
        )
        values = item.get("values", {})
        if not isinstance(values, dict):
            raise ValueError(
                f"Los valores enumerados del campo '{name}' "
                "deben ser un objeto."
            )

        fields.append(
            FieldConfig(
                name=str(name),
                type=str(field_type),
                scale=float(
                    item.get("scale", 1.0)
                ),
                value_offset=float(value_offset),
                byte_offset=byte_offset,
                byte_length=(
                    int(declared_length)
                    if declared_length is not None
                    else None
                ),
                values={
                    int(value): str(label)
                    for value, label in values.items()
                },
                expected_value=(
                    int(item["expected_value"])
                    if "expected_value" in item
                    else None
                ),
            )
        )

    sequence_field = frame_data.get("sequence_field")
    if sequence_field is None:
        sequence_field = next(
            (
                field_config.name
                for field_config in fields
                if field_config.name in ("frame_number", "sequence")
            ),
            None,
        )

    sync = parse_hex_bytes(frame_data.get("sync"))

    crc_data = frame_data.get("crc", {})
    if not isinstance(crc_data, dict):
        raise ValueError("frame.crc debe ser un objeto.")

    crc_enabled = crc_data.get("enabled", True)
    crc_type = (
        crc_data.get("algorithm", crc_data.get("type"))
        if crc_enabled
        else None
    )

    crc_size = (
        int(crc_data.get("length", crc_data.get("size", 0)))
        if crc_enabled
        else 0
    )
    crc_offset = crc_data.get("offset")
    crc_offset = int(crc_offset) if crc_offset is not None else None
    crc_endian_value = str(
        crc_data.get("byte_order", endian)
    ).lower()
    crc_endian = {
        "little_endian": "little",
        "big_endian": "big",
    }.get(crc_endian_value, crc_endian_value)
    if crc_endian not in ("little", "big"):
        raise ValueError("El byte order del CRC debe ser 'little' o 'big'.")

    crc_algorithm = (
        str(crc_type)
        .upper()
        .replace("-", "")
        .replace("_", "")
        .replace("/", "")
        if crc_type
        else None
    )
    if crc_algorithm not in (
        None,
        "CRC16CCITT",
        "CRC16CCITTFALSE",
    ):
        raise ValueError(f"CRC no implementado: {crc_type}")
    if crc_enabled and (
        crc_data.get("reflect_input", False)
        or crc_data.get("reflect_output", False)
    ):
        raise ValueError(
            "CRC con reflexión de bits no está implementado."
        )

    frame_length_value = frame_data.get("length")
    frame_length = (
        int(frame_length_value)
        if frame_length_value is not None
        else None
    )

    config = FrameConfig(
        endian=endian,
        fields=fields,
        sequence_field=sequence_field,
        sync=sync,
        crc_type=crc_type,
        crc_size=crc_size,
        frame_length=frame_length,
        crc_offset=crc_offset,
        crc_endian=crc_endian,
        crc_calculate_from=(
            int(crc_data["calculate_from"])
            if "calculate_from" in crc_data
            else None
        ),
        crc_calculate_to=(
            int(crc_data["calculate_to"])
            if "calculate_to" in crc_data
            else None
        ),
        crc_polynomial=int(crc_data.get("polynomial", 0x1021)),
        crc_initial_value=int(
            crc_data.get("initial_value", 0xFFFF)
        ),
        crc_final_xor=int(crc_data.get("final_xor", 0)),
    )

    if config.crc_type and config.crc_size <= 0:
        raise ValueError("El CRC está habilitado pero no tiene length/size.")
    if config.frame_length is not None and config.frame_length <= 0:
        raise ValueError("frame.length debe ser mayor que cero.")

    occupied = []
    for field_config in fields:
        field_offset = field_config.byte_offset
        if field_offset is None:
            continue
        end = field_offset + field_size(field_config)
        if field_offset < 0 or (
            config.frame_length is not None and end > config.frame_length
        ):
            raise ValueError(
                f"El campo '{field_config.name}' queda fuera de la trama."
            )
        if any(
            field_offset < previous_end and previous_start < end
            for previous_start, previous_end in occupied
        ):
            raise ValueError(
                f"El campo '{field_config.name}' se superpone con otro campo."
            )
        occupied.append((field_offset, end))

    if config.crc_offset is not None:
        crc_end = config.crc_offset + config.crc_size
        if (
            config.crc_offset < 0
            or (
                config.frame_length is not None
                and crc_end > config.frame_length
            )
        ):
            raise ValueError("El CRC queda fuera de la trama.")
        if any(
            config.crc_offset < field_end and field_start < crc_end
            for field_start, field_end in occupied
        ):
            raise ValueError("El CRC se superpone con un campo.")

    if config.frame_length is not None and not all(
        field_config.byte_offset is not None
        for field_config in fields
    ):
        raise ValueError(
            "Todos los campos necesitan offset cuando se define frame.length."
        )

    logger.info(
        "Frame configurado | payload=%d bytes | frame=%d bytes",
        config.payload_size,
        config.frame_size,
    )

    return config


def field_size(field_config: FieldConfig) -> int:
    if field_config.type == "bytes":
        return field_config.byte_length or 0

    return TYPE_FORMATS[field_config.type][1]


# ============================================================
# CRC
# ============================================================

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
                crc = (
                    (crc << 1) ^ polynomial
                ) & 0xFFFF
            else:
                crc = (
                    crc << 1
                ) & 0xFFFF

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
        crc_type.upper()
        .replace("-", "")
        .replace("_", "")
        .replace("/", "")
    )
    if crc_algorithm in ("CRC16CCITT", "CRC16CCITTFALSE"):

        if len(crc_bytes) != 2:
            return False

        calculated = crc16_ccitt(
            data,
            polynomial,
            initial_value,
            final_xor,
        )

        received = int.from_bytes(
            crc_bytes,
            byteorder=endian,
        )

        return calculated == received

    raise ValueError(
        f"CRC no implementado: {crc_type}"
    )


# ============================================================
# FRAME PARSER
# ============================================================

class FrameParser:

    def __init__(
        self,
        config: FrameConfig,
    ):
        self.config = config

        self.struct_prefix = (
            "<"
            if config.endian == "little"
            else ">"
        )

    def parse(
        self,
        frame: bytes,
    ) -> Optional[dict[str, Any]]:

        expected_size = self.config.frame_size

        if len(frame) != expected_size:
            logger.warning(
                "Frame con tamaño incorrecto: %d, esperado %d",
                len(frame),
                expected_size,
            )

            return None

        offset = 0

        # ----------------------------------------------------
        # SYNC
        # ----------------------------------------------------

        if self.config.sync:

            sync_size = len(
                self.config.sync
            )

            received_sync = frame[
                :sync_size
            ]

            if received_sync != self.config.sync:
                logger.warning(
                    "SYNC inválido: %s",
                    received_sync.hex(),
                )

                return None

            offset += sync_size

        # ----------------------------------------------------
        # CRC
        # ----------------------------------------------------

        if self.config.crc_type and self.config.crc_size:
            crc_offset = (
                self.config.crc_offset
                if self.config.crc_offset is not None
                else len(frame) - self.config.crc_size
            )
            crc_bytes = frame[
                crc_offset:crc_offset + self.config.crc_size
            ]
            calculate_from = (
                self.config.crc_calculate_from
                if self.config.crc_calculate_from is not None
                else 0
            )
            calculate_to = (
                self.config.crc_calculate_to
                if self.config.crc_calculate_to is not None
                else crc_offset - 1
            )
            if (
                calculate_from < 0
                or calculate_to < calculate_from
                or calculate_to >= len(frame)
            ):
                logger.warning("Rango de cálculo de CRC inválido")
                return None
            crc_data = frame[calculate_from:calculate_to + 1]

            if not validate_crc(
                crc_data,
                crc_bytes,
                self.config.crc_type,
                self.config.crc_endian or self.config.endian,
                self.config.crc_polynomial,
                self.config.crc_initial_value,
                self.config.crc_final_xor,
            ):
                logger.warning(
                    "CRC inválido"
                )

                return None

        result = {}
        payload_offset = offset

        for field_config in self.config.fields:

            struct_format, _ = TYPE_FORMATS[field_config.type]
            size = field_size(field_config)
            field_offset = (
                field_config.byte_offset
                if field_config.byte_offset is not None
                else payload_offset
            )
            if field_offset < 0 or field_offset + size > len(frame):
                logger.warning(
                    "Campo fuera de la trama: %s",
                    field_config.name,
                )
                return None

            if field_config.type in ("uint24", "int24"):
                raw_value = int.from_bytes(
                    frame[field_offset:field_offset + size],
                    byteorder=self.config.endian,
                    signed=field_config.type == "int24",
                )
            elif field_config.type == "bytes":
                raw_value = frame[field_offset:field_offset + size].hex()
            else:
                raw_value = struct.unpack_from(
                    self.struct_prefix + struct_format,
                    frame,
                    field_offset,
                )[0]

            if (
                field_config.expected_value is not None
                and raw_value != field_config.expected_value
            ):
                logger.warning(
                    "Valor inesperado para %s: %s, esperado %s",
                    field_config.name,
                    raw_value,
                    field_config.expected_value,
                )
                return None

            if field_config.type == "bytes":
                value = raw_value
            else:
                value = (
                    raw_value
                    * field_config.scale
                    + field_config.value_offset
                )

            # Evita devolver 10.0 cuando realmente es entero.
            if (
                field_config.scale == 1.0
                and field_config.value_offset == 0.0
                and field_config.type
                not in ("float32", "float64")
            ):
                value = raw_value

            result[field_config.name] = value
            if field_config.values:
                result[f"{field_config.name}_label"] = (
                    field_config.values.get(raw_value)
                )

            if field_config.byte_offset is None:
                payload_offset += size

        return result


# ============================================================
# FRAME BUFFER
# ============================================================

class FrameBuffer:

    def __init__(
        self,
        parser: FrameParser,
    ):
        self.parser = parser
        self.buffer = bytearray()
        self.invalid_frames = 0
        self.last_raw_frames: list[bytes] = []

    def feed(
        self,
        data: bytes,
    ) -> list[dict[str, Any]]:

        self.buffer.extend(data)

        frames = []
        self.last_raw_frames = []

        frame_size = (
            self.parser.config.frame_size
        )

        sync = (
            self.parser.config.sync
        )

        while True:

            if len(self.buffer) < frame_size:
                break

            # ------------------------------------------------
            # Buscar SYNC si está definido
            # ------------------------------------------------

            if sync:

                sync_index = self.buffer.find(
                    sync
                )

                if sync_index == -1:

                    # Conservamos solamente lo necesario
                    # para poder detectar un SYNC partido
                    # entre dos paquetes UART.
                    keep = max(
                        0,
                        len(sync) - 1,
                    )

                    if keep:
                        self.buffer = (
                            self.buffer[-keep:]
                        )
                    else:
                        self.buffer.clear()

                    break

                if sync_index > 0:

                    del self.buffer[
                        :sync_index
                    ]

                    if len(self.buffer) < frame_size:
                        break

            # ------------------------------------------------
            # Extraer frame
            # ------------------------------------------------

            raw_frame = bytes(
                self.buffer[
                    :frame_size
                ]
            )

            del self.buffer[
                :frame_size
            ]

            parsed = self.parser.parse(
                raw_frame
            )

            if parsed is not None:
                frames.append(parsed)
                self.last_raw_frames.append(raw_frame)
            else:
                self.invalid_frames += 1

        return frames


# ============================================================
# PACKET STATISTICS
# ============================================================

class PacketStatistics:

    def __init__(
        self,
        sequence_field: Optional[str],
    ):
        self.sequence_field = (
            sequence_field
        )

        self.received = 0
        self.lost = 0
        self.invalid = 0

        self.last_sequence = None

    def register(
        self,
        frame: dict[str, Any],
    ):

        self.received += 1

        if not self.sequence_field:
            return

        if (
            self.sequence_field
            not in frame
        ):
            return

        sequence = frame[
            self.sequence_field
        ]

        if self.last_sequence is None:

            self.last_sequence = sequence
            return

        expected = (
            self.last_sequence + 1
        )

        if sequence != expected:

            # Diferencia modular genérica.
            # El tamaño del contador dependerá del tipo
            # configurado, por eso solamente contabilizamos
            # saltos hacia adelante.
            if sequence > expected:

                self.lost += (
                    sequence - expected
                )

        self.last_sequence = sequence

    def snapshot(self) -> dict[str, Any]:

        total = (
            self.received
            + self.lost
        )

        loss_percent = (
            (self.lost / total) * 100
            if total
            else 0.0
        )

        return {
            "received": self.received,
            "lost": self.lost,
            "invalid": self.invalid,
            "loss_percent": loss_percent,
        }


# ============================================================
# DATABASE
# ============================================================

class Database:

    def __init__(
        self,
        path: str,
    ):
        self.path = Path(path)

        if not self.path.is_absolute():
            self.path = (
                BASE_DIR
                / self.path
            )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.connection = sqlite3.connect(
            self.path,
            check_same_thread=False,
        )

        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                sequence INTEGER,
                payload TEXT NOT NULL
            )
            """
        )

        self.connection.commit()

    def insert(
        self,
        data: dict[str, Any],
        sequence_field: Optional[str],
    ):

        sequence = None

        if sequence_field:
            sequence = data.get(
                sequence_field
            )

        self.connection.execute(
            """
            INSERT INTO telemetry (
                timestamp,
                sequence,
                payload
            )
            VALUES (?, ?, ?)
            """,
            (
                time.time(),
                sequence,
                json.dumps(
                    data,
                    ensure_ascii=False,
                ),
            ),
        )

        self.connection.commit()

    def close(self):

        self.connection.close()


# ============================================================
# CSV LOGGER
# ============================================================

class CSVLogger:

    def __init__(
        self,
        path: str,
        fields: list[str],
    ):

        self.path = Path(path)

        if not self.path.is_absolute():
            self.path = (
                BASE_DIR
                / self.path
            )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.fields = fields

        self.file = self.path.open(
            "a",
            newline="",
            encoding="utf-8",
        )

        self.writer = csv.DictWriter(
            self.file,
            fieldnames=[
                "timestamp",
                *self.fields,
            ],
        )

        if self.path.stat().st_size == 0:
            self.writer.writeheader()
            self.file.flush()

    def write(
        self,
        data: dict[str, Any],
    ):

        row = {
            "timestamp": time.time(),
        }

        for field_name in self.fields:
            row[field_name] = data.get(
                field_name
            )

        self.writer.writerow(row)
        self.file.flush()

    def close(self):

        self.file.close()


# ============================================================
# WEBSOCKET MANAGER
# ============================================================

class WebSocketManager:

    def __init__(self):

        self.clients: set[
            WebSocket
        ] = set()

        self.lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
    ):

        await websocket.accept()

        async with self.lock:
            self.clients.add(
                websocket
            )

        logger.info(
            "WebSocket conectado | clientes=%d",
            len(self.clients),
        )

    async def disconnect(
        self,
        websocket: WebSocket,
    ):

        async with self.lock:
            self.clients.discard(
                websocket
            )

        logger.info(
            "WebSocket desconectado | clientes=%d",
            len(self.clients),
        )

    async def broadcast(
        self,
        message: dict[str, Any],
    ):

        if not self.clients:
            return

        dead_clients = []

        async with self.lock:

            clients = list(
                self.clients
            )

        for websocket in clients:

            try:

                await websocket.send_json(
                    message
                )

            except Exception:

                dead_clients.append(
                    websocket
                )

        if dead_clients:

            async with self.lock:

                for websocket in dead_clients:
                    self.clients.discard(
                        websocket
                    )


# ============================================================
# RUNTIME STATE
# ============================================================

@dataclass
class RuntimeState:

    connected: bool = False

    last_frame: Optional[
        dict[str, Any]
    ] = None

    last_timestamp: Optional[
        float
    ] = None

    frames_received: int = 0
    last_raw_frame: Optional[str] = None
    last_crc_value: Optional[str] = None


# ============================================================
# GLOBAL STATE
# ============================================================

app_config: Optional[
    AppConfig
] = None

frame_config: Optional[
    FrameConfig
] = None

parser: Optional[
    FrameParser
] = None

frame_buffer: Optional[
    FrameBuffer
] = None

statistics: Optional[
    PacketStatistics
] = None

database: Optional[
    Database
] = None

csv_logger: Optional[
    CSVLogger
] = None

websocket_manager = (
    WebSocketManager()
)

runtime = RuntimeState()


# ============================================================
# ASYNC TASK HELPER
# ============================================================

background_tasks: set[
    asyncio.Task
] = set()


def create_background_task(
    coroutine,
):

    task = asyncio.create_task(
        coroutine
    )

    background_tasks.add(task)

    task.add_done_callback(
        background_tasks.discard
    )

    def log_task_exception(
        completed_task,
    ):

        try:
            completed_task.result()

        except asyncio.CancelledError:
            pass

        except Exception:
            logger.exception(
                "Error en tarea background"
            )

    task.add_done_callback(
        log_task_exception
    )

    return task


# ============================================================
# PROCESS FRAME
# ============================================================

async def process_frame(
    frame: dict[str, Any],
    raw_frame: Optional[bytes] = None,
):

    if statistics is None:
        return

    if database is None:
        return

    if csv_logger is None:
        return

    statistics.register(
        frame
    )

    database.insert(
        frame,
        frame_config.sequence_field
        if frame_config
        else None,
    )

    csv_logger.write(
        frame
    )

    runtime.last_frame = frame
    runtime.last_timestamp = time.time()
    runtime.frames_received += 1
    if raw_frame is not None:
        runtime.last_raw_frame = raw_frame.hex(" ").upper()
        if frame_config is not None and frame_config.crc_size:
            crc_offset = (
                frame_config.crc_offset
                if frame_config.crc_offset is not None
                else len(raw_frame) - frame_config.crc_size
            )
            crc_bytes = raw_frame[
                crc_offset:crc_offset + frame_config.crc_size
            ]
            runtime.last_crc_value = crc_bytes.hex().upper()

    snapshot = statistics.snapshot()
    snapshot["frames_received"] = runtime.frames_received

    await websocket_manager.broadcast(
        {
            "type": "telemetry",
            "timestamp": runtime.last_timestamp,
            "frame_length": (
                frame_config.frame_size
                if frame_config is not None
                else None
            ),
            "crc_valid": True,
            "crc_value": runtime.last_crc_value,
            "raw_hex": runtime.last_raw_frame,
            "data": frame,
            "statistics": snapshot,
        }
    )


# ============================================================
# SERIAL PROTOCOL
# ============================================================

class SerialProtocol(asyncio.Protocol):

    def __init__(self, loop):
        self.loop = loop
        self.transport = None
        self.disconnected = asyncio.Event()

    def connection_made(self, transport):

        self.transport = transport
        runtime.connected = True

        logger.info("UART conectada")

        create_background_task(
            websocket_manager.broadcast(
                {
                    "type": "connection",
                    "connected": True,
                }
            )
        )

    def data_received(self, data: bytes):

        if frame_buffer is None or statistics is None:
            return

        if not data:
            return

        logger.debug(
            "UART RX: %s",
            data.hex(" "),
        )

        try:

            frames = frame_buffer.feed(data)
            previous_invalid = statistics.invalid
            statistics.invalid = frame_buffer.invalid_frames

            for frame, raw_frame in zip(
                frames,
                frame_buffer.last_raw_frames,
            ):
                create_background_task(
                    process_frame(frame, raw_frame)
                )
            if statistics.invalid > previous_invalid:
                create_background_task(
                    websocket_manager.broadcast(
                        {
                            "type": "statistics",
                            "statistics": statistics.snapshot(),
                        }
                    )
                )

        except Exception:
            logger.exception(
                "Error procesando datos UART"
            )

    def connection_lost(self, exc):

        runtime.connected = False

        if exc:
            logger.error(
                "UART desconectada | %r | tipo=%s",
                exc,
                type(exc).__name__,
            )
        else:
            logger.warning(
                "UART desconectada | sin excepción"
            )

        self.disconnected.set()

        create_background_task(
            websocket_manager.broadcast(
                {
                    "type": "connection",
                    "connected": False,
                }
            )
        )

# ============================================================
# SERIAL LOOP
# ============================================================

async def serial_loop():

    while True:

        if app_config is None:
            await asyncio.sleep(1)
            continue

        transport = None
        protocol = None

        try:

            logger.info(
                "Conectando UART %s @ %d",
                app_config.serial.port,
                app_config.serial.baudrate,
            )

            loop = asyncio.get_running_loop()

            transport, protocol = (
                await serial_asyncio.create_serial_connection(
                    loop,
                    lambda: SerialProtocol(loop),
                    app_config.serial.port,
                    baudrate=app_config.serial.baudrate,
                )
            )

            logger.info(
                "Puerto UART abierto correctamente"
            )

            # IMPORTANTE:
            # Esperamos a que connection_lost() indique
            # realmente que la UART se desconectó.
            await protocol.disconnected.wait()

        except asyncio.CancelledError:

            logger.info(
                "Serial loop cancelado"
            )

            if transport is not None:
                transport.close()

            raise

        except Exception:

            runtime.connected = False

            logger.exception(
                "Error en UART"
            )

        finally:

            runtime.connected = False

            if transport is not None:

                try:
                    transport.close()
                except Exception:
                    pass

        logger.info(
            "Reintentando UART en %.1f segundos",
            app_config.serial.reconnect_delay,
        )

        await asyncio.sleep(
            app_config.serial.reconnect_delay
        )

# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Estación Terrena de Telemetría",
    version="1.0.0",
)
app.mount(
    "/frontend",
    StaticFiles(directory=FRONTEND_DIR),
    name="frontend",
)


# ============================================================
# HTTP ROUTES
# ============================================================

@app.get("/")
async def root():

    index_file = FRONTEND_DIR / "index.html"

    if not index_file.exists():

        logger.error(
            "Frontend no encontrado: %s",
            index_file,
        )

        return {
            "error": "Frontend no encontrado",
            "path": str(index_file),
        }

    return FileResponse(
        index_file
    )


@app.get("/api/status")
async def status():

    return {
        "connected": runtime.connected,
        "frames_received": runtime.frames_received,
        "last_timestamp": runtime.last_timestamp,
        "serial_port": (
            app_config.serial.port
            if app_config is not None
            else None
        ),
        "baudrate": (
            app_config.serial.baudrate
            if app_config is not None
            else None
        ),
        "statistics": (
            statistics.snapshot()
            if statistics
            else {}
        ),
    }


@app.get("/api/telemetry")
async def telemetry():

    return {
        "connected": runtime.connected,
        "timestamp": runtime.last_timestamp,
        "data": runtime.last_frame,
        "frame_length": (
            frame_config.frame_size
            if frame_config is not None
            else None
        ),
        "crc_valid": runtime.last_frame is not None,
        "crc_value": runtime.last_crc_value,
        "raw_hex": runtime.last_raw_frame,
        "statistics": (
            statistics.snapshot()
            if statistics
            else {}
        ),
    }


@app.websocket("/ws/telemetry")
@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
):

    await websocket_manager.connect(
        websocket
    )

    try:

        # Enviar inmediatamente el estado actual.
        await websocket.send_json(
            {
                "type": "connection",
                "connected": runtime.connected,
            }
        )

        if runtime.last_frame is not None:

            await websocket.send_json(
                {
                    "type": "telemetry",
                    "timestamp": runtime.last_timestamp,
                    "frame_length": (
                        frame_config.frame_size
                        if frame_config is not None
                        else None
                    ),
                    "crc_valid": True,
                    "crc_value": runtime.last_crc_value,
                    "raw_hex": runtime.last_raw_frame,
                    "data": runtime.last_frame,
                    "statistics": (
                        statistics.snapshot()
                        if statistics
                        else {}
                    ),
                }
            )

        # Mantener abierta la conexión.
        while True:

            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    except Exception:

        logger.exception(
            "Error WebSocket"
        )

    finally:

        await websocket_manager.disconnect(
            websocket
        )


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup():

    global app_config
    global frame_config
    global parser
    global frame_buffer
    global statistics
    global database
    global csv_logger

    logger.info(
        "Inicializando Ground Station..."
    )

    # --------------------------------------------------------
    # CONFIG
    # --------------------------------------------------------

    app_config = load_app_config()

    frame_config = (
        load_frame_config()
    )

    parser = FrameParser(
        frame_config
    )

    frame_buffer = FrameBuffer(
        parser
    )

    statistics = PacketStatistics(
        frame_config.sequence_field
    )

    # --------------------------------------------------------
    # STORAGE
    # --------------------------------------------------------

    database = Database(
        app_config.storage.database
    )

    csv_logger = CSVLogger(
        app_config.storage.csv,
        [
            output_name
            for frame_field in frame_config.fields
            for output_name in (
                [frame_field.name, f"{frame_field.name}_label"]
                if frame_field.values
                else [frame_field.name]
            )
        ],
    )

    logger.info(
        "Base de datos: %s",
        database.path,
    )

    logger.info(
        "CSV: %s",
        csv_logger.path,
    )

    # --------------------------------------------------------
    # UART
    # --------------------------------------------------------

    create_background_task(
        serial_loop()
    )

    logger.info(
        "Ground Station iniciada"
    )


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def shutdown():

    runtime.connected = False

    logger.info(
        "Cerrando Ground Station..."
    )

    # Cancelar tareas background.
    current_task = (
        asyncio.current_task()
    )

    tasks_to_cancel = [
        task
        for task in background_tasks
        if task is not current_task
    ]

    for task in tasks_to_cancel:
        task.cancel()

    if tasks_to_cancel:

        await asyncio.gather(
            *tasks_to_cancel,
            return_exceptions=True,
        )

    if database is not None:

        try:
            database.close()

        except Exception:
            logger.exception(
                "Error cerrando SQLite"
            )

    if csv_logger is not None:

        try:
            csv_logger.close()

        except Exception:
            logger.exception(
                "Error cerrando CSV"
            )

    logger.info(
        "Ground Station cerrada"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    # Cargar configuración solamente para obtener
    # host/puerto del servidor HTTP.
    startup_config = load_app_config()

    uvicorn.run(
        app,
        host=startup_config.websocket.host,
        port=startup_config.websocket.port,
        log_level="info",
    )