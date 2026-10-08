# Estación Terrena de Telemetría

Aplicación de estación terrena para un cohete. Recibe tramas binarias por puerto serie, las valida y decodifica según una definición YAML, las guarda (SQLite y CSV) y las muestra en un dashboard web en tiempo real.

## Características

- Lectura asíncrona del puerto serie con reconexión automática.
- Tramas definidas por YAML (`config/frame.yaml`): cambiar el formato no requiere modificar código.
- Validación de largo, CRC-16/CCITT-FALSE y valores esperados.
- Estadísticas del enlace: paquetes recibidos, perdidos, tasa y tiempo desde el último paquete.
- Persistencia en SQLite y CSV.
- Dashboard web (tema claro de alto contraste) vía WebSocket: barómetro, altitud, aceleración XYZ, mapa/GPS, salud del enlace e hitos de vuelo.

## Requisitos

- Python 3.10 o superior
- Un dispositivo que envíe la trama por puerto serie (por ejemplo, `/dev/ttyACM0` en Linux o `COMx` en Windows)

## Instalación

```bash
# Crear y activar el entorno virtual
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# Instalar dependencias
pip install -r requirements.txt
```

## Configuración

Editar [`config/app.yaml`](config/app.yaml):

```yaml
serial:
  port: "/dev/ttyACM0"   # Windows: "COM6"
  baudrate: 115200
  reconnect_delay: 3     # segundos entre reintentos

websocket:
  host: "0.0.0.0"
  port: 8000

storage:
  database: "telemetry.db"
  csv: "telemetry.csv"
```

> En Linux, el usuario debe tener permiso sobre el puerto serie:
> `sudo usermod -aG dialout $USER` (requiere cerrar sesión y volver a entrar).

El formato de la trama se define en [`config/frame.yaml`](config/frame.yaml) (30 bytes, big endian, CRC-16 en los bytes 28–29). El esquema completo está documentado en [`config.md`](config.md).

## Ejecución

```bash
python main.py
```

Luego abrir el dashboard en <http://localhost:8000>.

Si el puerto serie no está disponible, el servidor igualmente arranca e intenta reconectar cada `reconnect_delay` segundos.

## Endpoints

| Ruta | Descripción |
|---|---|
| `GET /` | Dashboard web |
| `GET /api/status` | Estado del sistema y del enlace |
| `GET /api/telemetry` | Última telemetría recibida |
| `WS /ws/telemetry` (también `/ws`) | Stream de telemetría en tiempo real |

## Estructura del proyecto

```text
.
├── main.py              # Backend (FastAPI + serie + parser + almacenamiento)
├── config/
│   ├── app.yaml         # Puerto serie, servidor y almacenamiento
│   └── frame.yaml       # Definición de la trama
├── frontend/
│   ├── index.html       # Dashboard
│   ├── css/style.css
│   └── assets/          # Logo
├── config.md            # Especificación del esquema de tramas
├── front.md             # Especificación del dashboard
└── requirements.txt
```

## Datos generados

`telemetry.db` y `telemetry.csv` se crean al ejecutar y están excluidos de git (ver `.gitignore`).

## Documentación adicional

- [`config.md`](config.md): cómo definir tramas, campos, escalado y CRC.
- [`front.md`](front.md): diseño y requisitos del dashboard.
