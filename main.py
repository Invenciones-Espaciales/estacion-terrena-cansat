import asyncio
import sqlite3
import struct
from datetime import datetime, timezone
from pathlib import Path

import serial
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel


# ============================================================
# CONFIGURACIÓN
# ============================================================

SERIAL_PORT = "COM6"
BAUD_RATE = 115200

DB_PATH = "data/telemetry.db"

PACKET_SIZE = 22
ROCKET_ID = 0x01
HEADER = 0x01

MPU_SCALE = 16384.0


# ============================================================
# MODELO
# ============================================================

class Telemetry(BaseModel):
    flight_id: int
    rocket_id: int
    frame: int
    timestamp_ms: int

    accel_x: float
    accel_y: float
    accel_z: float

    pressure: int
    temperature: float

    state: int
    received_at: datetime


# ============================================================
# WEBSOCKET MANAGER
# ============================================================

class WebSocketManager:

    def __init__(self):
        self.connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)

        print(
            f"[WS] Cliente conectado. "
            f"Clientes: {len(self.connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)

        print(
            f"[WS] Cliente desconectado. "
            f"Clientes: {len(self.connections)}"
        )

    async def broadcast(self, data: dict):

        disconnected = []

        for websocket in list(self.connections):

            try:
                await websocket.send_json(data)

            except Exception:
                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(websocket)


# ============================================================
# DATABASE
# ============================================================

def get_db():

    Path(DB_PATH).parent.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(DB_PATH)

    connection.row_factory = sqlite3.Row

    return connection


def init_database():

    with get_db() as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS flights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rocket_id INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                flight_id INTEGER NOT NULL,
                rocket_id INTEGER NOT NULL,

                frame INTEGER NOT NULL,
                timestamp_ms INTEGER NOT NULL,

                accel_x REAL NOT NULL,
                accel_y REAL NOT NULL,
                accel_z REAL NOT NULL,

                pressure INTEGER NOT NULL,
                temperature REAL NOT NULL,

                state INTEGER NOT NULL,

                received_at TEXT NOT NULL,

                FOREIGN KEY (
                    flight_id
                ) REFERENCES flights(id)
            )
        """)

        db.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_telemetry_flight
            ON telemetry(flight_id)
        """)

        db.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_telemetry_timestamp
            ON telemetry(
                flight_id,
                timestamp_ms
            )
        """)

        db.commit()

    print("[DB] Base de datos inicializada")


def create_flight(rocket_id: int) -> int:

    now = datetime.now(
        timezone.utc
    ).isoformat()

    with get_db() as db:

        cursor = db.execute(
            """
            INSERT INTO flights (
                rocket_id,
                started_at
            )
            VALUES (?, ?)
            """,
            (
                rocket_id,
                now
            )
        )

        db.commit()

        return cursor.lastrowid


def save_telemetry(telemetry: Telemetry):

    with get_db() as db:

        db.execute(
            """
            INSERT INTO telemetry (
                flight_id,
                rocket_id,
                frame,
                timestamp_ms,

                accel_x,
                accel_y,
                accel_z,

                pressure,
                temperature,

                state,
                received_at
            )
            VALUES (
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?
            )
            """,
            (
                telemetry.flight_id,
                telemetry.rocket_id,
                telemetry.frame,
                telemetry.timestamp_ms,

                telemetry.accel_x,
                telemetry.accel_y,
                telemetry.accel_z,

                telemetry.pressure,
                telemetry.temperature,

                telemetry.state,
                telemetry.received_at.isoformat(),
            )
        )

        db.commit()


# ============================================================
# CRC
# ============================================================

def crc16_ccitt(data: bytes) -> int:

    crc = 0xFFFF

    for byte in data:

        crc ^= byte << 8

        for _ in range(8):

            if crc & 0x8000:

                crc = (
                    (crc << 1)
                    ^ 0x1021
                ) & 0xFFFF

            else:

                crc = (
                    crc << 1
                ) & 0xFFFF

    return crc


# ============================================================
# DECODIFICACIÓN
# ============================================================

def decode_packet(
    packet: bytes,
    flight_id: int
):

    if len(packet) != PACKET_SIZE:
        return None

    # Header
    if packet[0] != ROCKET_ID:
        return None

    if packet[1] != HEADER:
        return None

    # CRC recibido
    received_crc = struct.unpack(
        ">H",
        packet[20:22]
    )[0]

    # CRC calculado
    calculated_crc = crc16_ccitt(
        packet[:20]
    )

    if received_crc != calculated_crc:

        print(
            "[CRC] Paquete inválido"
        )

        return None

    # Frame
    frame = struct.unpack(
        ">H",
        packet[2:4]
    )[0]

    # Timestamp
    timestamp_ms = struct.unpack(
        ">I",
        packet[4:8]
    )[0]

    # Accelerometer
    accel_x_raw = struct.unpack(
        ">h",
        packet[8:10]
    )[0]

    accel_y_raw = struct.unpack(
        ">h",
        packet[10:12]
    )[0]

    accel_z_raw = struct.unpack(
        ">h",
        packet[12:14]
    )[0]

    # Pressure 24 bits
    pressure = (
        (packet[14] << 16)
        | (packet[15] << 8)
        | packet[16]
    )

    # Temperature
    temperature_raw = struct.unpack(
        ">h",
        packet[17:19]
    )[0]

    # State
    state = packet[19]

    return Telemetry(

        flight_id=flight_id,

        rocket_id=packet[0],

        frame=frame,

        timestamp_ms=timestamp_ms,

        accel_x=(
            accel_x_raw
            / MPU_SCALE
        ),

        accel_y=(
            accel_y_raw
            / MPU_SCALE
        ),

        accel_z=(
            accel_z_raw
            / MPU_SCALE
        ),

        pressure=pressure,

        temperature=(
            temperature_raw / 10.0
        ),

        state=state,

        received_at=datetime.now(
            timezone.utc
        )
    )


# ============================================================
# SERIAL
# ============================================================

class SerialReceiver:

    def __init__(
        self,
        port,
        baudrate,
        flight_id,
        websocket_manager
    ):

        self.port = port

        self.baudrate = baudrate

        self.flight_id = flight_id

        self.websocket_manager = (
            websocket_manager
        )

        self.running = False

        self.serial = None

    async def start(self):

        self.running = True

        print(
            f"[SERIAL] Abriendo {self.port}"
        )

        try:

            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1
            )

        except serial.SerialException as e:

            print(
                f"[SERIAL] Error: {e}"
            )

            return

        buffer = bytearray()

        print(
            "[SERIAL] Esperando telemetría..."
        )

        while self.running:

            data = await asyncio.to_thread(
                self.serial.read,
                self.serial.in_waiting or 1
            )

            if not data:

                await asyncio.sleep(
                    0.001
                )

                continue

            buffer.extend(data)

            while len(buffer) >= PACKET_SIZE:

                # Buscar inicio de trama
                start = -1

                for i in range(
                    len(buffer) - 1
                ):

                    if (
                        buffer[i]
                        == ROCKET_ID
                        and
                        buffer[i + 1]
                        == HEADER
                    ):

                        start = i

                        break

                if start == -1:

                    buffer = buffer[-1:]

                    break

                # Eliminar basura
                if start > 0:

                    del buffer[:start]

                if len(buffer) < PACKET_SIZE:
                    break

                packet = bytes(
                    buffer[:PACKET_SIZE]
                )

                del buffer[
                    :PACKET_SIZE
                ]

                telemetry = decode_packet(
                    packet,
                    self.flight_id
                )

                if telemetry is None:
                    continue

                # ====================================
                # GUARDAR
                # ====================================

                save_telemetry(
                    telemetry
                )

                # ====================================
                # WEBSOCKET
                # ====================================

                await (
                    self.websocket_manager
                    .broadcast(
                        telemetry.model_dump(
                            mode="json"
                        )
                    )
                )

                print(
                    f"[TELEMETRY] "
                    f"Frame={telemetry.frame} "
                    f"Time={telemetry.timestamp_ms}ms "
                    f"P={telemetry.pressure}Pa "
                    f"T={telemetry.temperature:.1f}C"
                )

    def stop(self):

        self.running = False

        if (
            self.serial
            and self.serial.is_open
        ):

            self.serial.close()

            print(
                "[SERIAL] Puerto cerrado"
            )


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Rocket Telemetry",
    version="1.0.0"
)

ws_manager = WebSocketManager()

serial_receiver = None


# ============================================================
# STARTUP / SHUTDOWN
# ============================================================

@app.on_event("startup")
async def startup():

    global serial_receiver

    print(
        "================================"
    )

    print(
        " ROCKET TELEMETRY BACKEND"
    )

    print(
        "================================"
    )

    # DB
    init_database()

    # Crear vuelo
    flight_id = create_flight(
        ROCKET_ID
    )

    print(
        f"[FLIGHT] Vuelo creado: "
        f"{flight_id}"
    )

    # Serial
    serial_receiver = SerialReceiver(

        port=SERIAL_PORT,

        baudrate=BAUD_RATE,

        flight_id=flight_id,

        websocket_manager=ws_manager
    )

    asyncio.create_task(
        serial_receiver.start()
    )


@app.on_event("shutdown")
async def shutdown():

    if serial_receiver:

        serial_receiver.stop()


# ============================================================
# WEBSOCKET
# ============================================================

@app.websocket(
    "/ws/telemetry"
)
async def websocket_endpoint(
    websocket: WebSocket
):

    await ws_manager.connect(
        websocket
    )

    try:

        while True:

            # Mantenemos la conexión abierta.
            # El frontend puede mandar "ping"
            # si quiere.

            await websocket.receive_text()

    except WebSocketDisconnect:

        ws_manager.disconnect(
            websocket
        )

    except Exception:

        ws_manager.disconnect(
            websocket
        )


# ============================================================
# REST - HISTÓRICO
# ============================================================

@app.get("/api/flights")
def get_flights():

    with get_db() as db:

        rows = db.execute(
            """
            SELECT
                id,
                rocket_id,
                started_at,
                ended_at
            FROM flights
            ORDER BY id DESC
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]


@app.get(
    "/api/flights/{flight_id}/telemetry"
)
def get_telemetry(
    flight_id: int
):

    with get_db() as db:

        rows = db.execute(
            """
            SELECT *
            FROM telemetry

            WHERE flight_id = ?

            ORDER BY timestamp_ms
            """,
            (flight_id,)
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "serial_port": SERIAL_PORT,
        "baudrate": BAUD_RATE
    }


# ============================================================
# EJECUCIÓN DIRECTA
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )