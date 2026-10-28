# Protocolo de Telemetría y Telecomandos CanSat CONAE (2026–2027)

> **Idioma / Language:** [ 🇪🇸 Español ](protocol.md) | [ 🇬🇧 English ](../protocol.md)

Este documento describe la especificación técnica autorizada del protocolo de telemetría y telecomandos entre la aviónica de vuelo del CanSat y la Estación Terrena, en estricto cumplimiento con las **Bases CONAE §4–§7** y los requerimientos del Anexo Técnico **G1–G15, X1–X6, C3–C5, F1–F5**.

---

## 1. Resumen General del Protocolo

La arquitectura de comunicaciones del CanSat utiliza un enlace de radiofrecuencia bidireccional operando en las bandas ISM autorizadas en Argentina por ENACOM (915–928 MHz o 2.4 GHz, requerimiento **X1**), con direccionamiento punto a punto (**X2**, sin modo broadcast).

| Parámetro | Especificación | Requerimiento Oficial |
| :--- | :--- | :--- |
| **Frecuencia de Transmisión** | 1 paquete por segundo ($1\,\text{Hz}$) | **C5, X4** |
| **Formato de Transmisión** | Texto plano separado por comas (ASCII CSV) | **Bases CONAE §4, G5** |
| **Resolución Tiempo de Misión**| $1\,\text{segundo}$ (UTC `hh:mm:ss`) | **G3, F2** |
| **Secuencia de Paquetes** | Monótonamente creciente, persistente ante reinicios | **F1** |
| **Direccionamiento** | Punto a punto con prefijo de equipo (`TEAM_ID='1000'`) | **X2** |
| **Bandas de Frecuencia** | 915–928 MHz (autorizada libre por ENACOM) | **X1** |
| **Comandos de Subida** | Cadenas ASCII (`CMD,TEAM_ID,COMMAND`) | **G15, G1, F3, F5, X6** |
| **Salida Dual CSV** | `Flight_XXXX.csv` (computadora local y disco de respaldo) | **G2** |

---

## 2. Estructura de la Trama de Telemetría

Cada paquete de telemetría es una cadena de texto ASCII finalizada con retorno de carro y salto de línea (`\r\n` o `\n`):

```text
TEAM_ID, MISSION_TIME, PACKET_COUNT, MODE, STATE, ALTITUDE, TEMPERATURE, PRESSURE, VOLTAGE, CURRENT, GYRO_R, GYRO_P, GYRO_Y, ACCEL_R, ACCEL_P, ACCEL_Y, GPS_TIME, GPS_ALTITUDE, GPS_LATITUDE, GPS_LONGITUDE, GPS_SATS, CMD_ECHO [,,OPTIONAL_DATA]
```

### Definición de Campos y Unidades de Ingeniería

| Índice | Campo | Tipo | Resolución / Unidades | Descripción y Requerimiento Oficial |
| :---: | :--- | :---: | :---: | :--- |
| 0 | `TEAM_ID` | String | 4 dígitos | Identificación del equipo asignado (ej. `'1000'`). |
| 1 | `MISSION_TIME` | String | $1\,\text{s}$ (`hh:mm:ss`) | Tiempo UTC de misión (**G3, F2**). |
| 2 | `PACKET_COUNT` | Entero | 1 paquete | Total transmitido; persiste ante reinicios (**F1**). |
| 3 | `MODE` | Char | `'F'` o `'S'` | Modo vuelo (`'F'`) o modo simulación (`'S'`). |
| 4 | `STATE` | String | Enum ASCII | Estado de vuelo: `'LAUNCH_PAD'`, `'ASCENT'`, `'APOGEE'`, `'DESCENT'`, `'LANDED'`. |
| 5 | `ALTITUDE` | Float | $0.1\,\text{m}$ | Altitud relativa al nivel de la plataforma (**X5, G1**). |
| 6 | `TEMPERATURE` | Float | $0.1\,^\circ\text{C}$ | Temperatura ambiental del sensor (**X5**). |
| 7 | `PRESSURE` | Float | $0.1\,\text{kPa}$ | Presión estática barométrica (**X5**). |
| 8 | `VOLTAGE` | Float | $0.1\,\text{V}$ | Voltaje del bus principal de batería (**G7**). |
| 9 | `CURRENT` | Float | $0.01\,\text{A}$ | Corriente de descarga de batería (**G7**). |
| 10 | `GYRO_R` | Float | $0.1\,^\circ\text{/s}$ | Tasa de rotación en Roll (**X5**). |
| 11 | `GYRO_P` | Float | $0.1\,^\circ\text{/s}$ | Tasa de rotación en Pitch (**X5**). |
| 12 | `GYRO_Y` | Float | $0.1\,^\circ\text{/s}$ | Tasa de rotación en Yaw (**X5**). |
| 13 | `ACCEL_R` | Float | $0.01\,\text{m/s}^2$ | Aceleración en eje Roll (**X5**). |
| 14 | `ACCEL_P` | Float | $0.01\,\text{m/s}^2$ | Aceleración en eje Pitch (**X5**). |
| 15 | `ACCEL_Y` | Float | $0.01\,\text{m/s}^2$ | Aceleración en eje Yaw (**X5**). |
| 16 | `GPS_TIME` | String | $1\,\text{s}$ (`hh:mm:ss`) | Hora UTC del receptor GNSS (**X5**). |
| 17 | `GPS_ALTITUDE` | Float | $0.1\,\text{m}$ | Altitud GNSS sobre nivel medio del mar (**X5**). |
| 18 | `GPS_LATITUDE` | Float | $0.0001^\circ$ | Latitud decimal Norte WGS84 (**X5**). |
| 19 | `GPS_LONGITUDE`| Float | $0.0001^\circ$ | Longitud decimal Oeste WGS84 (**X5**). |
| 20 | `GPS_SATS` | Entero | 1 satélite | Satélites GNSS en seguimiento (**X5**). |
| 21 | `CMD_ECHO` | String | Texto ASCII | Eco del último comando ejecutado (**G15, X3**). |
| 22 | `OPTIONAL_DATA`| String | Tras `,,` | Carga útil científica opcional (ej. `SOLAR_V:4.92`). |

---

## 3. Especificación de Telecomandos (Estación $\to$ CanSat)

Los telecomandos enviados desde la Estación Terrena utilizan el prefijo estándar `CMD,<TEAM_ID>,<ACTION>[,<ARGS>]\r\n`:

```text
CMD,1000,CAL\r\n           --> Calibración de altitud a cero en plataforma (G1).
CMD,1000,ST,13:14:02\r\n   --> Sincronización del reloj RTC a hora oficial UTC (F3).
CMD,1000,PC,0\r\n          --> Reinicio del contador persistente de paquetes (F1, F5).
CMD,1000,BATT\r\n          --> Solicitud de telemetría de batería y paneles solares (X6, G7).
CMD,1000,SIM,ENABLE\r\n    --> Habilitación de modo simulación (Bases §4).
CMD,1000,START\r\n         --> Disparo manual de inicio de misión / separación (X3).
```

---

## 4. Métricas de Enlace y Conteo de Paquetes (G14 y G8)

1. **Contador de Paquetes Recibidos (`RX_COUNT`, G14):**
   La estación terrena contabiliza de forma independiente cada paquete recibido y validado con $\ge 22$ columnas.
2. **Contador de Paquetes Perdidos (`LOST_COUNT`, G8):**
   Calculado automáticamente ante saltos en la secuencia `PACKET_COUNT` del CanSat:
   $$\text{Si } \text{PACKET\_COUNT}_k > \text{PACKET\_COUNT}_{k-1} + 1 \implies \text{Perdidos} \mathrel{+}= \text{PACKET\_COUNT}_k - (\text{PACKET\_COUNT}_{k-1} + 1)$$
   $$\%\text{ Pérdida} = \frac{\text{Perdidos}}{\text{RX\_COUNT} + \text{Perdidos}} \times 100\%$$
3. **Verificación de Velocidad de Descenso ($V_z$):**
   $$V_z = \frac{\text{ALTITUD}_k - \text{ALTITUD}_{k-1}}{t_k - t_{k-1}}$$
   - **Fase C3:** $-18.0\,\text{m/s} \le V_z \le -12.0\,\text{m/s}$ ($15 \pm 3\,\text{m/s}$).
   - **Fase C4:** $-8.0\,\text{m/s} \le V_z \le -2.0\,\text{m/s}$ ($5 \pm 3\,\text{m/s}$).
