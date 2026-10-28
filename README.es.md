# Estación Terrena CanSat CONAE (2026–2027)

> **Idioma / Language:** [ 🇪🇸 Español ](README.es.md) | [ 🇬🇧 English ](README.md)

Estación terrena de adquisición, procesamiento y telecomandos en tiempo real desarrollada para la **Competencia CanSat CONAE 2026–2027**, en cumplimiento riguroso de las **Bases §4–§7** y el **Anexo de Requerimientos Técnicos (G1–G15, X1–X6, C1–C9, E1–E7, S1–S8)**.

---

## Resumen de Cumplimiento Técnico

| Req. ID | Especificación | Implementación en la Estación Terrena | Estado |
| :--- | :--- | :--- | :--- |
| **G13** | **GUI Única (Sin Pestañas)** | Toda la telemetría, 5 gráficos, mapa, terminal y controles visibles simultáneamente sin pestañas ni cambio de vistas. | **CUMPLE** |
| **G12** | **Legibilidad a Plena Luz Solar** | Tema claro de alto contraste (texto negro `#000000` sobre `#ffffff`/`#f1f5f9`), tipografía $\ge 14\,\text{pt}$ (18.66 px), ejes gruesos (`lineWidth: 2`) y trazos en negrita (`lineWidth: 3`). | **CUMPLE** |
| **G5** | **Telemetría en Texto en Tiempo Real** | Terminal ASCII en la parte inferior transmitiendo cadenas CSV sin procesar a 1 Hz durante ascenso y descenso. | **CUMPLE** |
| **G6** | **Unidades del Sistema Internacional** | Cada métrica e instrumento indica explícitamente sus unidades SI (`m`, `°C`, `kPa`, `V`, `A`, `m/s²`, `°/s`, `m/s`, `sats`). | **CUMPLE** |
| **G7** | **5 Gráficos en Tiempo Real** | Graficación en tiempo real de: (1) Altitud, (2) Voltaje de batería, (3) Corriente de batería, (4) Acelerómetro 3 ejes, (5) Giroscopio 3 ejes. | **CUMPLE** |
| **G8** | **Telemetría de Misión** | Visualización en tiempo real de Tiempo de Misión UTC (`hh:mm:ss`), Temperatura, Posición GPS, Paquetes RX, Paquetes Perdidos y Estado de Software. | **CUMPLE** |
| **G14** | **Contador de Paquetes RX** | La estación mantiene un contador independiente `RX_COUNT` para contabilizar tramas recibidas con éxito. | **CUMPLE** |
| **G15 / G1** | **Subida de Telecomandos** | Consola interactiva para calibración de altitud a cero (`CMD,1000,CAL`), sincronización horaria UTC (`CMD,1000,ST`), reinicio de contador, consulta de batería y simulación. | **CUMPLE** |
| **G2** | **Registro Dual CSV Flushed** | Grabación instantánea en `data/Flight_1000.csv` (computadora) y `data/backup/Flight_1000.csv` (disco de respaldo / pendrive USB) con `os.fsync`. | **CUMPLE** |
| **C3 / C4** | **Velocidad de Descenso** | Cálculo de velocidad vertical ($V_z = \Delta h / \Delta t$) en tiempo real verificando límites C3 ($15 \pm 3\,\text{m/s}$) y C4 ($5 \pm 3\,\text{m/s}$). | **CUMPLE** |
| **X1 / X2** | **Regulaciones de Radio** | Operación en banda 915–928 MHz (ENACOM), direccionamiento punto a punto (P2P con prefijo `TEAM_ID`, sin broadcast). | **CUMPLE** |

---

## Informe de Revisión Preliminar de Diseño (PDR)

El informe técnico exhaustivo con el análisis de alternativas de enlace de radio, antenas, interfaces eléctricas, presupuesto de enlace y resolución de ambigüedades (TBR/TBD) se encuentra en:
* **[docs/pdr_tradeoff_report.md](docs/pdr_tradeoff_report.md)**

---

## Protocolo de Telemetría Oficial (CSV Plano CONAE)

La estación procesa telemetría a 1 Hz correspondiente al formato estándar oficial:

```text
TEAM_ID, MISSION_TIME, PACKET_COUNT, MODE, STATE, ALTITUDE, TEMPERATURE, PRESSURE, VOLTAGE, CURRENT, GYRO_R, GYRO_P, GYRO_Y, ACCEL_R, ACCEL_P, ACCEL_Y, GPS_TIME, GPS_ALTITUDE, GPS_LATITUDE, GPS_LONGITUDE, GPS_SATS, CMD_ECHO [,,OPTIONAL_DATA]
```

---

## Inicio Rápido

### 1. Entorno Virtual
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Pruebas Automatizadas
```bash
python -m unittest discover tests
```

### 3. Ejecución de la Estación Terrena
```bash
.venv/bin/python main.py
```
Acceder mediante navegador a: **`http://localhost:8080`**

### 4. Simulador de CanSat (PTY Virtual)
```bash
python3 scripts/cansat_simulator.py
```
