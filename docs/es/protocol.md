# Especificación del Protocolo Binario de Telemetría (Trama LoRa de 65 Bytes)

> **Idioma / Language:** [ 🇪🇸 Español ](protocol.md) | [ 🇬🇧 English ](../protocol.md)

---

## 1. Resumen Ejecutivo y Características Físicas

La Estación Terrena opera con una trama binaria compacta y determinista de **65 bytes**, optimizada para enlaces de radiofrecuencia (RF) de largo alcance mediante modulación LoRa (transceptores Semtech SX1276 / SX1278).

### Parámetros Nominales del Enlace de Radio (Capa Física)

| Parámetro | Valor Nominal de Misión | Justificación Técnica |
|---|---|---|
| **Frecuencia Central** | $433.000\text{ MHz}$ / $915.000\text{ MHz}$ | Banda ISM libre de licencia reglamentaria. |
| **Ancho de Banda (BW)** | $125\text{ kHz}$ / $250\text{ kHz}$ | Equilibrio óptimo entre sensibilidad térmica ($-148\text{ dBm}$) y tasa de datos. |
| **Factor de Ensanchamiento (SF)** | $\text{SF7}$ o $\text{SF8}$ | Tiempos de transmisión breves ($T_{\text{air}} \approx 65\text{ ms}$) minimizando colisiones en vuelo supersónico. |
| **Tasa de Código (CR)** | $4/5$ | Protección de corrección de errores por código convolucional con mínima sobrecarga ($25\%$). |
| **Tasa de Transmisión Nominal** | $10\text{ Hz}$ ($100\text{ ms}$) | Frecuencia de muestreo suficiente para reconstruir la trayectoria balística y el apogeo. |
| **Ancho de Banda de Datos Neto** | $650\text{ bytes/s}$ ($5.2\text{ kbps}$) | Muy por debajo de la capacidad de canal a SF7 ($5.47\text{ kbps}$ netos). |

---

## 2. Mapa de Memoria Estructurado (65 Bytes)

Todos los campos numéricos de múltiples bytes están codificados en **Little-Endian** estándar (orden byte menos significativo primero, estándar ARM Cortex-M / AVR / x86).

```text
0                   1                   2                   3
0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   SYNC=0xAA   |       FRAME_NUMBER (uint16)   |  TIMESTAMP... |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| ...TIMESTAMP (uint32)         | STATUS (uint8)|  PRESSURE...  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| ...PRESSURE (float32)         | ALTURA_ACTUAL (float32)       |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| ACCEL_X (float32)             | ACCEL_Y (float32)             |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| ACCEL_Z (float32)             | GYRO_X (float32)              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| GYRO_Y (float32)              | GYRO_Z (float32)              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| TEMP_IMU (float32)            | LATITUDE (float32)            |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| LONGITUDE (float32)           | ALTITUD_GPS (float32)         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| SATS (uint8)  | GROUND_SPEED (float32)        | PIN_F | PIN_P |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| CRC-16 (uint16, bytes 63-64)  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

### Tabla de Descriptores de Campos

| Byte Offset | Campo | Tipo | Bytes | Unidades | Rango / Resolución | Descripción |
|---|---|---|---|---|---|---|
| `0` | `sync` | `uint8` | 1 | Constante | `0xAA` | Byte de sincronización de trama fija. |
| `1 - 2` | `frame_number` | `uint16` | 2 | Contador | $0 - 65,535$ | Contador secuencial de trama para detección de paquetes perdidos. |
| `3 - 6` | `timestamp` | `uint32` | 4 | $\text{ms}$ | $0 - 4,294,967,295$ | Tiempo de funcionamiento de aviónica desde encendido (`millis()`). |
| `7` | `status` | `uint8` | 1 | Enumerado | `0x00 - 0xFF` | Máquina de estados de vuelo de aviónica (ver sección 3). |
| `8 - 11` | `pressure` | `float32` | 4 | $\text{hPa}$ | $300.0 - 1100.0$ | Presión atmosférica absoluta medida por sensor BMP280. |
| `12 - 15` | `altura_actual` | `float32` | 4 | $\text{m}$ | $-100.0 - 15000.0$ | Altitud barométrica calculada en el vehículo respecto a plataforma. |
| `16 - 19` | `accel_x` | `float32` | 4 | $\text{g}$ | $\pm 16.0$ | Aceleración en eje transversal X ($1\text{ g} = 9.80665\text{ m/s}^2$). |
| `20 - 23` | `accel_y` | `float32` | 4 | $\text{g}$ | $\pm 16.0$ | Aceleración en eje transversal Y. |
| `24 - 27` | `accel_z` | `float32` | 4 | $\text{g}$ | $\pm 16.0$ | Aceleración en eje longitudinal Z (vector de empuje). |
| `28 - 31` | `gyro_x` | `float32` | 4 | $\text{deg/s}$ | $\pm 2000.0$ | Velocidad angular de balanceo/alabeo (eje X). |
| `32 - 35` | `gyro_y` | `float32` | 4 | $\text{deg/s}$ | $\pm 2000.0$ | Velocidad angular de cabeceo (eje Y). |
| `33 - 39` | `gyro_z` | `float32` | 4 | $\text{deg/s}$ | $\pm 2000.0$ | Velocidad angular de guiñada (eje Z). |
| `40 - 43` | `temp_imu` | `float32` | 4 | $^{\circ}\text{C}$ | $-40.0 - +85.0$ | Temperatura de matriz de silicio IMU (MPU6050 / BMI088). |
| `44 - 47` | `latitude` | `float32` | 4 | Grados dec. | $\pm 90.000000$ | Latitud geodésica WGS-84 obtenida por GPS. |
| `48 - 51` | `longitude` | `float32` | 4 | Grados dec. | $\pm 180.000000$ | Longitud geodésica WGS-84 obtenida por GPS. |
| `52 - 55` | `altitud_gps` | `float32` | 4 | $\text{m}$ | $-100.0 - 20000.0$ | Altitud elipsoidal o MSL reportada por receptor GNSS. |
| `56` | `satellites` | `uint8` | 1 | Conteo | $0 - 32$ | Número de satélites GNSS activos en la solución de navegación. |
| `57 - 60` | `ground_speed`| `float32` | 4 | $\text{m/s}$ | $0.0 - 500.0$ | Velocidad horizontal sobre el suelo calculada por Doppler GNSS. |
| `61` | `pin_frenado` | `uint8` | 1 | Booleano | $0$ o $1$ | Estado del canal de disparo pirotécnico de paracaídas de frenado (Drogue). |
| `62` | `pin_principal`| `uint8` | 1 | Booleano | $0$ o $1$ | Estado del canal de disparo pirotécnico de paracaídas principal. |
| `63 - 64` | `crc` | `uint16` | 2 | Suma de verif. | `0x0000 - 0xFFFF` | Suma de verificación CRC-16/CCITT-FALSE calculada sobre bytes `0..62`. |

---

## 3. Máquina de Estados de Vuelo (`status`)

El byte de estado en el offset 7 codifica la fase de vuelo de la computadora de abordo:

| Valor Hex | Etiqueta | Descripción de la Fase de Vuelo |
|---|---|---|
| `0x00` | `STANDBY` | Vehículo en plataforma de lanzamiento. Sistemas nominales, adquisición activa, en espera de detección de despegue ($a_z > 2.5\text{ g}$). |
| `0x01` | `POWERED` | Vuelo propulsado. Motor encendido, aceleración longitudinal positiva intensa ($3\text{ g} - 12\text{ g}$). |
| `0x03` | `BURNOUT` | Fin de combustión / Costa balística. Aceleración longitudinal negativa por resistencia aerodinámica ($a_z < 0\text{ g}$), ascenso inercial al apogeo. |
| `0x07` | `APOGEE` | Detección de apogeo. Velocidad vertical nula ($V_z \approx 0$), máxima altitud registrada. |
| `0x0F` | `DROGUE_ORD` | Comando de expulsión de paracaídas de frenado (Drogue) emitido. Pin pirotécnico energizado (`pin_frenado = 1`). |
| `0x1F` | `DROGUE_CONF` | Descenso estabilizado bajo paracaídas de frenado a alta velocidad ($\sim 30 - 50\text{ m/s}$). |
| `0x3F` | `MAIN_ORD` | Comando de expulsión de paracaídas principal emitido a altitud barométrica objetivo ($\sim 400 - 500\text{ m}$). Pin pirotécnico energizado (`pin_principal = 1`). |
| `0x7F` | `MAIN_CONF` | Descenso terminal suave bajo paracaídas principal ($\sim 4 - 7\text{ m/s}$). |
| `0xFF` | `LANDED` | Impacto en tierra confirmado (altitud constante durante $> 10\text{ s}$, aceleración en reposo $1.0\text{ g}$). Modo baliza acústica y radial activo. |

---

## 4. Algoritmo de Integridad CRC-16/CCITT-FALSE

Para garantizar inmunidad frente a ruido impulsivo, interferencias electromagnéticas del encendido pirotécnico y desvanecimientos RF en trayectoria balística, la trama implementa una suma de verificación **CRC-16/CCITT-FALSE**.

### Parámetros Matemáticos del CRC

$$\text{Polinomio Génesis: } P(x) = x^{16} + x^{12} + x^5 + 1 \quad (\text{Valor hexadecimal: } 0x1021)$$

- **Valor Inicial ($\text{Init}$):** `0xFFFF`
- **XOR Final ($\text{XorOut}$):** `0x0000`
- **Reflexión de Entrada ($\text{RefIn}$):** Falsa (sin inversión de bits)
- **Reflexión de Salida ($\text{RefOut}$):** Falsa (sin inversión de bits)
- **Rango de Cálculo:** Bytes `0` a `62` inclusive (63 bytes en total)
- **Ubicación en Trama:** Bytes `63` y `64` en formato Little-Endian

### Implementación en C / Arduino

```c
uint16_t crc16_ccitt_false(const uint8_t *data, size_t length) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < length; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (uint8_t bit = 0; bit < 8; bit++) {
            if (crc & 0x8000) {
                crc = (crc << 1) ^ 0x1021;
            } else {
                crc = crc << 1;
            }
        }
    }
    return crc;
}
```

---

## 5. Documentación Relacionada

- **[Definición Declarativa de la Trama (YAML)](frame-schema.md):** Esquema dinámico de parsing en `config/frame.yaml`.
- **[Arquitectura End-to-End del Sistema](architecture.md):** Flujo de datos asíncrono desde el puerto serie hasta la interfaz web.
- **[Especificación de la API y WebSocket](api.md):** Endpoints REST y mensajes JSON de telemetría en tiempo real.
- **[Manual de Operaciones e Instalación](getting-started.md):** Puesta en marcha, simulación por software y solución de problemas.
