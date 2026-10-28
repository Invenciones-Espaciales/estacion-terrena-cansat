# Arquitectura del Sistema de Estación Terrena CanSat CONAE

> **Idioma / Language:** [ 🇪🇸 Español ](architecture.md) | [ 🇬🇧 English ](../architecture.md)

Este documento describe la arquitectura software y hardware, el pipeline asíncrono, la persistencia dual de datos y el motor de visualización de la **Estación Terrena CanSat CONAE 2026–2027**.

---

## 1. Visión General del Sistema

La Estación Terrena es un sistema asíncrono de alto rendimiento desarrollado en **Python 3.11+**, **FastAPI**, **`pyserial-asyncio`**, y un motor de visualización Canvas HTML5 sin dependencias pesadas.

```mermaid
graph TD
    subgraph Capa Física / Enlace de Radio
        CS[CanSat Aviónica de Vuelo] <-->|Enlace RF 915 MHz| GSTR[Transceptor de Estación]
        GSTR <-->|USB UART /dev/ttyACM0| OS[Driver Serie Linux]
    end

    subgraph Núcleo Backend (main.py)
        OS <-->|pyserial-asyncio| SP[Protocolo CanSatSerialProtocol]
        SP --> AP[Parser CanSatAsciiParser 1 Hz]
        AP --> PROC[Pipeline process_telemetry]
        
        PROC --> DB[(Base de Datos SQLite telemetry.db)]
        PROC --> DUAL_CSV[(Dual CSV Logger: Flight_1000.csv)]
        DUAL_CSV --> D1[Disco Primario: data/]
        DUAL_CSV --> D2[Disco Respaldo: data/backup/]
        PROC --> STAT[Estadísticas PacketStatistics G14/G8]
        PROC --> WSM[Distribuidor WebSocketManager]
        
        CMD_EP[POST /api/command] -->|Telecomandos de Subida| SP
    end

    subgraph Capa de Presentación (GUI Única - Sin Pestañas, Cero Scroll)
        WSM <-->|WebSocket ws://localhost:8080/ws| WS_CLIENT[Cliente WebSocket]
        WS_CLIENT --> C1[1. Gráfico Altitud Barométrica]
        WS_CLIENT --> C2[2. Gráfico Tensión Batería]
        WS_CLIENT --> C3[3. Gráfico Corriente Batería]
        WS_CLIENT --> C4[4. Gráfico Aceleraciones 3 Ejes]
        WS_CLIENT --> C5[5. Gráfico Tasas de Rotación]
        WS_CLIENT --> MAP[Mapa de Posición GPS Leaflet]
        WS_CLIENT --> TERM[Consola Telemetría Texto Plano G5]
        WS_CLIENT --> CMD_PANEL[Panel de Telecomandos G15/G1]
    end
```

---

## 2. Ingesta Asíncrona y Modelo de Concurrencia

### Adquisición Serie (`CanSatSerialProtocol`)
Se ejecuta directamente en el bucle de eventos `asyncio` sin bloquear hilos:
* Los bytes leídos se dividen por delimitadores de línea (`\r\n` o `\n`).
* Cada línea se procesa en una estructura tipada `CanSatTelemetry`.
* Los telecomandos se inyectan en el buffer de transmisión de forma transparente.

### Persistencia Dual y Entrega Inmediata (Requerimiento G2)
* Los datos se escriben simultáneamente en dos rutas independientes:
  - Principal: `data/Flight_1000.csv`
  - Respaldo (Pendrive USB): `data/backup/Flight_1000.csv`
* Cada trama ejecuta `flush()` y `os.fsync()` garantizando que la memoria no volátil esté actualizada para la entrega física a los evaluadores inmediatamente después del aterrizaje.
* Endpoint directo de descarga rápida: `GET /api/export/csv`.

---

## 3. Interfaz Solar de Pantalla Única (G13, G12)

1. **Sin Pestañas (G13):** Toda la información de sensores, los 5 gráficos en tiempo real, el mapa y los controles residen en una sola vista.
2. **Cero Scroll:** La interfaz se autoajusta dinámicamente al $100\%$ de la ventana (`100vh`, `overflow: hidden`) en pantallas de campo ($1366 \times 768$ y $1920 \times 1080$).
3. **Visibilidad a Plena Luz Solar (G12):**
   - Tipografía mínima $\ge 14\,\text{pt}$ ($18.66\,\text{px}$) en métricas.
   - Tema claro de alto contraste (texto negro sobre fondo blanco puro).
   - Trazos gruesos en gráficos (ejes $2.0\,\text{px}$, líneas $3.0\,\text{px}$).
