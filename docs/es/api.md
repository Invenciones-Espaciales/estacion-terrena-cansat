# Especificación de la API REST y Protocolo WebSocket

> **Idioma / Language:** [ 🇪🇸 Español ](api.md) | [ 🇬🇧 English ](../api.md)

---

## 1. Visión General y URLs Base

El servidor de la Estación Terrena opera sobre **FastAPI** y el servidor ASGI de alto rendimiento **Uvicorn**. Por defecto, se enlaza a todas las interfaces de red locales en el puerto `8000`:

- **URL Base HTTP:** `http://localhost:8000` (o `http://<ip-estacion>:8000`)
- **URL WebSocket:** `ws://localhost:8000/ws/telemetry` (alias corto disponible: `ws://localhost:8000/ws`)
- **Estándares:** HTTP/1.1, WebSocket RFC 6455
- **Tipo de Contenido:** `application/json` (endpoints API) y `text/html; charset=utf-8` (vistas web)

---

## 2. Endpoints de la API REST

### 2.1 Vista Principal del Dashboard Web
Entrega la aplicación web de monitoreo de telemetría de página única (SPA).

- **Ruta:** `GET /`
- **Autenticación:** Ninguna
- **Respuesta:** Archivo HTML estático `frontend/index.html` (`200 OK`)

---

### 2.2 Consola Pre-Vuelo Go / No-Go
Entrega la consola de calificación previa al despegue, validando baselines de sensores, contadores de estabilidad de plataforma y límites meteorológicos.

- **Ruta:** `GET /gonogo`
- **Autenticación:** Ninguna
- **Respuesta:** Archivo HTML `frontend/gonogo.html` (`200 OK`)

---

### 2.3 Consola de Búsqueda y Recuperación (Recovery)
Entrega la vista orientada a misiones de rescate post-impacto, con visualización de coordenadas GPS, cálculo de rumbo (bearing) y distancia geodésica.

- **Ruta:** `GET /recovery`
- **Autenticación:** Ninguna
- **Respuesta:** Archivo HTML `frontend/recovery.html` (`200 OK`)

---

### 2.4 Estado del Enlace y Salud del Sistema
Devuelve el estado operativo de la estación, conexión con el puerto serie UART, parámetros de calificación Go/No-Go y métricas estadísticas de transmisión.

- **Ruta:** `GET /api/status`
- **Método:** `GET`
- **Tipo de Respuesta:** `application/json`

#### Ejemplo de Respuesta (`200 OK`):
```json
{
  "connected": true,
  "frames_received": 1420,
  "last_timestamp": 1713148922.45,
  "serial_port": "/dev/ttyUSB0",
  "baudrate": 115200,
  "statistics": {
    "received": 1420,
    "frames_received": 1420,
    "lost": 3,
    "invalid": 1,
    "loss_percent": 0.2108
  },
  "gonogo": {
    "required_hold_s": 30.0,
    "altitude_tol_m": 5.0,
    "accel_xy_tol_g": 0.1,
    "accel_z_nominal_g": 1.0,
    "accel_z_tol_g": 0.15,
    "gps_radius_m": 5.0,
    "weather_limits": {
      "max_wind_speed_ms": 10.0,
      "max_cloud_cover_pct": 75.0,
      "min_visibility_km": 5.0
    }
  }
}
```

---

### 2.5 Última Trama de Telemetría Recibida
Devuelve la instantánea más reciente recibida, decodificada y validada, junto con su representación hexadecimal cruda y el estado de la suma de verificación.

- **Ruta:** `GET /api/telemetry`
- **Método:** `GET`
- **Tipo de Respuesta:** `application/json`

#### Ejemplo de Respuesta (`200 OK`):
```json
{
  "connected": true,
  "timestamp": 1713148922.45,
  "data": {
    "sync": 170,
    "frame_number": 105,
    "timestamp": 155400,
    "status": 1,
    "status_label": "POWERED",
    "pressure": 995.4,
    "altura_actual": 152.8,
    "accel_x": 0.15,
    "accel_y": -0.12,
    "accel_z": 4.85,
    "gyro_x": 1.25,
    "gyro_y": -0.85,
    "gyro_z": 45.0,
    "temp_imu": 31.5,
    "latitude": -34.6038,
    "longitude": -58.3817,
    "altitud_gps": 177.8,
    "satellites": 14,
    "ground_speed": 18.6,
    "pin_frenado": 1,
    "pin_principal": 0
  },
  "frame_length": 65,
  "crc_valid": true,
  "crc_value": "3F12",
  "raw_hex": "AA 69 00 18 5F 02 00 01 CD CC 78 44 66 66 19 43 9A 99 19 3E 7B 14 F6 BD 66 66 9B 40 00 00 A0 3F 9A 99 59 BF 00 00 34 42 00 00 FC 41 87 6A 0A C2 31 82 69 C2 CD CC 31 43 0E CD CC 94 41 01 00 12 3F",
  "statistics": {
    "received": 105,
    "frames_received": 105,
    "lost": 0,
    "invalid": 0,
    "loss_percent": 0.0
  }
}
```

---

### 2.6 Consulta de Historial Temporal
Devuelve las tramas recibidas en los últimos $N$ segundos para hidratar gráficos y vistas sin pérdida de continuidad.

- **Ruta:** `GET /api/history`
- **Parámetros de Consulta:**
  - `seconds` (float, por defecto `60.0`): Ventana temporal en segundos hacia atrás.
  - `limit` (int, por defecto `1200`): Límite máximo de tramas devueltas.

---

## 3. Protocolo WebSocket en Tiempo Real

Para lograr una latencia inferior a $10\text{ ms}$, el servidor emite mensajes en formato JSON a todos los clientes conectados a través de WebSocket.

### Conexión:
```text
ws://localhost:8000/ws/telemetry
```

### Eventos Emitidos por el Servidor:

#### 1. Evento de Telemetría (`type: "telemetry"`)
Emitido cada vez que se recibe, valida y parsea una trama binaria legítima:
```json
{
  "type": "telemetry",
  "timestamp": 1713148922.45,
  "frame_length": 65,
  "crc_valid": true,
  "crc_value": "3F12",
  "raw_hex": "AA 69 00 ...",
  "data": {
    "frame_number": 105,
    "timestamp": 155400,
    "status": 1,
    "status_label": "POWERED",
    "pressure": 995.4,
    "altura_actual": 152.8,
    "accel_x": 0.15,
    "accel_y": -0.12,
    "accel_z": 4.85,
    "gyro_x": 1.25,
    "gyro_y": -0.85,
    "gyro_z": 45.0,
    "temp_imu": 31.5,
    "latitude": -34.6038,
    "longitude": -58.3817,
    "altitud_gps": 177.8,
    "satellites": 14,
    "ground_speed": 18.6,
    "pin_frenado": 1,
    "pin_principal": 0
  },
  "statistics": {
    "received": 105,
    "frames_received": 105,
    "lost": 0,
    "invalid": 0,
    "loss_percent": 0.0
  }
}
```

#### 2. Evento de Estado de Conexión (`type: "connection"`)
Emitido inmediatamente al conectar o desconectar el puerto UART:
```json
{
  "type": "connection",
  "connected": true
}
```

#### 3. Evento de Actualización Estadística (`type: "statistics"`)
Emitido cuando se detectan tramas corruptas o saltos en la numeración:
```json
{
  "type": "statistics",
  "statistics": {
    "received": 105,
    "lost": 2,
    "invalid": 1,
    "loss_percent": 1.869
  }
}
```

---

## 4. Documentación Relacionada

- **[Especificación del Protocolo Binario](protocol.md):** Mapa de memoria y detalles de trama.
- **[Arquitectura del Sistema](architecture.md):** Diseño del bucle de eventos y gestión de clientes.
- **[Manual de Operaciones](getting-started.md):** Ejecución con virtualización serie.
