# Estación Terrena de Telemetría para Cohetes

> **Idioma / Language:** [ 🇪🇸 Español ](README.es.md) | [ 🇬🇧 English ](README.md)

Una estación terrena de telemetría modular y asíncrona diseñada para cohetería experimental y de sondeo. La plataforma adquiere tramas binarias de telemetría de alta frecuencia a través de un enlace serie (UART/USB/módem RF), valida la integridad de cada paquete mediante CRC-16/CCITT-FALSE, decodifica los campos dinámicamente según especificaciones declarativas en YAML, persiste los datos simultáneamente en SQLite y CSV plano, y difunde las métricas en tiempo real a un tablero web de alto contraste mediante WebSockets.

---

## Suite de Documentación Técnica

La documentación técnica completa está disponible en **Español** e **Inglés** bajo [`docs/es/`](docs/es/) y [`docs/`](docs/):

| Documento (Español) | Document (English) | Descripción |
|---|---|---|
| **[Arquitectura del Sistema](docs/es/architecture.md)** | **[System Architecture](docs/architecture.md)** | Pipeline de flujo de datos, concurrencia asíncrona (`asyncio`) y motor de renderizado desacoplado. |
| **[Protocolo Binario](docs/es/protocol.md)** | **[Protocol Specification](docs/protocol.md)** | Estructura de la trama LoRa de 65 bytes, mapa de memoria a nivel de bit, estados de vuelo y CRC-16. |
| **[Esquema de Trama (YAML)](docs/es/frame-schema.md)** | **[Frame Schema](docs/frame-schema.md)** | Especificación declarativa en YAML: propiedades de campos, escalamiento y reglas del decodificador. |
| **[Tablero y Frontend](docs/es/frontend-dashboard.md)** | **[Dashboard Specification](docs/frontend-dashboard.md)** | Disposición visual en grid, instrumentos Canvas (cinta de altitud, osciloscopios) y ergonomía. |
| **[API y WebSockets](docs/es/api.md)** | **[API Specification](docs/api.md)** | Endpoints REST (`GET /`, `/gonogo`, `/api/status`), esquemas JSON y streaming WebSocket. |
| **[Guía de Inicio y Operaciones](docs/es/getting-started.md)** | **[Getting Started](docs/getting-started.md)** | Configuración para desarrolladores, permisos serie en Linux (`dialout`) y pruebas con virtualización. |
| **[Guía de Contribución](CONTRIBUTING.es.md)** | **[Contributing Guide](CONTRIBUTING.md)** | Manual de incorporación para nuevos ingenieros, flujo Git, estándares de código y PR. |
| **[Compilación Windows (.exe)](docs/es/packaging-exe.md)** | **[Windows Packaging](docs/packaging-exe.md)** | Generación de ejecutable independiente con PyInstaller, `build_windows.bat` o GitHub Actions. |
| **[Cálculos Futuros](docs/es/calculos-futuros.md)** | **[Future Calculations](docs/calculos-futuros.md)** | Filtro de Kalman 1D, variómetro ($V_z$), elipse de aterrizaje y normas de alarma ISA-18.2. |
| **[Limpieza Pendiente](docs/es/pending-deletions-list.md)** | **[Pending Cleanups](docs/pending-deletions-list.md)** | Inventario de archivos reubicados y propuestos para revisión. |

---

## Características Principales

- **Motor Serie Asíncrono:** Adquisición no bloqueante con `pyserial-asyncio` con reconexión automática en caliente ante desconexión física de la antena o cable USB.
- **Protocolo Declarativo por Esquema:** La estructura binaria está gobernada íntegramente por [`config/frame.yaml`](config/frame.yaml). Modificar campos o formatos no requiere tocar código Python.
- **Verificación Cripto-Aritmética Estricta:** Longitud fija de trama forzada, suma de verificación CRC-16/CCITT-FALSE y sincronización por cabecera (`0xAA`) con inmunidad al ruido.
- **Diagnóstico Cuantitativo del Enlace:** Detección de paquetes perdidos por numeración secuencial, porcentaje en tiempo real, frecuencia instantánea de recepción (Hz) y detección de silencio.
- **Doble Persistencia Inmediata:** Registro paralelo en base de datos SQLite indexada (`data/telemetry.db`) y archivo CSV plano append-only con vaciado inmediato a disco (`data/telemetry.csv`).
- **Tablero de Misión de Alto Contraste:** Instrumentos Canvas 2D sin dependencias externas (cinta móvil de altitud aeroespacial, osciloscopios temporales), mapas GPS con Leaflet y alarmas visuales ISA-18.2 legibles bajo luz solar directa.
- **Consola Pre-Vuelo Go / No-Go:** Vista especializada (`/gonogo`) para validación de baselines en plataforma, estabilidad de sensores y límites climáticos de lanzamiento.
- **Simulador de Misión en Microcontrolador:** Firmware de 290 segundos listo para flashear en [`arduino/telemetry_simulator/`](arduino/telemetry_simulator/) para simulación hardware-in-the-loop (HIL).

---

## Requisitos del Sistema

- **Python:** 3.10 o superior (Python 3.11+ recomendado).
- **Sistemas Operativos:** Linux (Debian, Ubuntu, Raspberry Pi OS), Windows 10/11, macOS.
- **Hardware Soportado:** Cualquier transceptor serie o convertidor USB a UART (CP2102, FTDI, CH340, módems LoRa, radios SiK).

---

## Inicio Rápido

### 1. Configurar Permisos Serie en Linux
```bash
sudo usermod -aG dialout $USER
newgrp dialout
```

### 2. Configurar Entorno Virtual e Instalar Dependencias
```bash
# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate       # En Linux / macOS
# .venv\Scripts\activate        # En Windows

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Ejecutar Pruebas Automatizadas
Verifica que el entorno y el decodificador pasan el 100% de las pruebas:
```bash
python tests/test_telemetry_65b.py
# O mediante unittest:
python -m unittest discover tests
```

### 4. Configurar Enlace de Hardware
Edita [`config/app.yaml`](config/app.yaml) con tu puerto serie y velocidad en baudios:
```yaml
serial:
  port: "/dev/ttyACM0"   # Windows: "COM6", Linux: "/dev/ttyUSB0"
  baudrate: 115200
  reconnect_delay: 3     # Tiempo de espera para reintentar (segundos)

websocket:
  host: "0.0.0.0"        # Escuchar en todas las interfaces de red
  port: 8000

storage:
  database: "data/telemetry.db"
  csv: "data/telemetry.csv"
```

### 5. Iniciar la Estación Terrena
```bash
python main.py
```
Abre tu navegador en:
- **`http://localhost:8000`** $\to$ Tablero de misión en tiempo real
- **`http://localhost:8000/gonogo`** $\to$ Consola de calificación pre-vuelo Go / No-Go
- **`http://localhost:8000/recovery`** $\to$ Vista de recuperación y coordenadas GPS post-impacto

---

## Resumen de la API

| Endpoint | Protocolo | Descripción |
|---|---|---|
| `GET /` | HTTP | Entrega el tablero web principal (`frontend/index.html`) |
| `GET /gonogo` | HTTP | Entrega la consola pre-vuelo Go / No-Go (`frontend/gonogo.html`) |
| `GET /recovery` | HTTP | Entrega la consola de búsqueda y rescate (`frontend/recovery.html`) |
| `GET /api/history` | HTTP | Historial de telemetría de los últimos $N$ segundos (por defecto 60s) |
| `GET /api/status` | HTTP | Estado de salud, enlace serie y estadísticas de paquetes |
| `GET /api/telemetry` | HTTP | Última trama recibida, decodificada y representación hexadecimal |
| `WS /ws/telemetry` | WebSocket | Transmisión bidireccional continua de telemetría en tiempo real |
| `WS /ws` | WebSocket | Alias de streaming para `/ws/telemetry` |

*Para esquemas y ejemplos completos, consulta la [Documentación de la API](docs/es/api.md).*

---

## Estructura del Proyecto

```text
.
├── main.py                  # Núcleo de la estación (FastAPI + serial_asyncio + decodificador + persistencia)
├── arduino/                 # Firmware de simulación para microcontrolador (Arduino / ESP32)
│   └── telemetry_simulator/ # Código de simulación de vuelo de 290 segundos
├── config/
│   ├── app.yaml             # Configuración de puerto serie, red y base de datos
│   └── frame.yaml           # Esquema declarativo de trama de 65 bytes y CRC
├── data/                    # Registros de misiones generados en tiempo real (ignorado en Git)
│   ├── telemetry.db         # Base de datos SQLite
│   └── telemetry.csv        # Registro plano en CSV
├── docs/                    # Suite de documentación técnica en Inglés y Español
│   ├── es/                  # Documentación completa en Español
│   │   ├── api.md
│   │   ├── architecture.md
│   │   ├── calculos-futuros.md
│   │   ├── frame-schema.md
│   │   ├── frontend-dashboard.md
│   │   ├── getting-started.md
│   │   ├── packaging-exe.md
│   │   ├── pending-deletions-list.md
│   │   └── protocol.md
│   ├── api.md               # Versiones en Inglés
│   ├── architecture.md
│   └── ...
├── frontend/                # Tablero web (HTML5 Canvas + Leaflet + CSS)
│   ├── index.html           # Tablero de misión de página única
│   ├── gonogo.html          # Consola pre-vuelo Go / No-Go
│   ├── recovery.html        # Vista de recuperación y GPS post-impacto
│   ├── css/style.css        # Hojas de estilo
│   └── assets/              # Gráficos y logotipos
├── tests/
│   ├── __init__.py          # Marcador de paquete de pruebas
│   └── test_telemetry_65b.py# Suite automatizada (parser, CRC, ventana deslizante, BD)
├── build_windows.bat        # Compilador de 1 clic para ejecutable de Windows
├── ground_station.spec      # Especificación para PyInstaller
├── CONTRIBUTING.md          # Guía de contribución para el equipo (Inglés)
├── CONTRIBUTING.es.md       # Guía de contribución en Español
├── README.md                # Entrada principal del proyecto (Inglés)
├── README.es.md             # Entrada principal en Español
└── requirements.txt         # Dependencias Python
```

---

## Contribución y Nuevos Desarrolladores

¡Todas las contribuciones del equipo son bienvenidas! Antes de abrir un pull request, por favor revisa la [Guía de Contribución](CONTRIBUTING.es.md) para conocer las pautas de configuración, normas de código y pruebas requeridas.

---

## Licencia y Créditos

Desarrollado para el monitoreo de aviónica de cohetes de sondeo por el equipo de ingeniería de la Estación Terrena.
