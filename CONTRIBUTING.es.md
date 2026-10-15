# Guía de Contribución a la Estación Terrena de Telemetría

> **Idioma / Language:** [ 🇪🇸 Español ](CONTRIBUTING.es.md) | [ 🇬🇧 English ](CONTRIBUTING.md)

¡Te damos la bienvenida al equipo de desarrollo de la **Estación Terrena de Telemetría de Cohetes** (`estacion-terrena-pc`)!

Este proyecto está construido para monitorear en tiempo real la aviónica de cohetes experimentales y de sondeo. Esta guía resume todo lo necesario para comenzar, comprender la arquitectura del sistema, escribir código y pruebas con altos estándares de calidad, seguir nuestro flujo de trabajo en Git y colaborar en equipo de manera eficiente.

---

## Tabla de Contenidos

1. [Guía Rápida de Incorporación (Onboarding)](#1-guía-rápida-de-incorporación-onboarding)
2. [Estructura del Repositorio y Arquitectura](#2-estructura-del-repositorio-y-arquitectura)
3. [Flujo de Trabajo con Git y Estrategia de Ramas](#3-flujo-de-trabajo-con-git-y-estrategia-de-ramas)
4. [Estándares de Lenguaje y Documentación](#4-estándares-de-lenguaje-y-documentación)
5. [Estilo de Código y Convenciones de Ingeniería](#5-estilo-de-código-y-convenciones-de-ingeniería)
6. [Pruebas Automatizadas y Control de Calidad](#6-pruebas-automatizadas-y-control-de-calidad)
7. [Simuladores y Desarrollo sin Hardware Físico](#7-simuladores-y-desarrollo-sin-hardware-físico)
8. [Proceso de Pull Request (PR) y Revisión](#8-proceso-de-pull-request-pr-y-revisión)
9. [Empaquetado y Distribución para Windows](#9-empaquetado-y-distribución-para-windows)

---

## 1. Guía Rápida de Incorporación (Onboarding)

Sigue estos pasos para poner en marcha un entorno local funcional en menos de 5 minutos:

### 1.1 Requisitos Previos
- **Python:** Versión 3.10 o superior (Python 3.11+ recomendado).
- **Sistema Operativo:** Linux (Debian, Ubuntu, Raspberry Pi OS), Windows 10/11 o macOS.
- **Git:** Cliente de línea de comandos estándar.
- **Navegador Web:** Chrome, Firefox, Edge o Safari.

### 1.2 Paso 1: Clonar y Configurar Entorno Virtual
```bash
# Clonar el repositorio
git clone https://github.com/tu-organizacion/estacion-terrena-pc.git
cd estacion-terrena-pc

# Crear entorno virtual aislado
python3 -m venv .venv

# Activar entorno virtual
source .venv/bin/activate       # En Linux / macOS
# .venv\Scripts\activate        # En Windows

# Actualizar pip e instalar dependencias de ejecución
pip install --upgrade pip
pip install -r requirements.txt
```

### 1.3 Paso 2: Permisos del Puerto Serie (Solo Linux)
```bash
sudo usermod -aG dialout $USER
newgrp dialout
```

### 1.4 Paso 3: Ejecutar la Suite de Pruebas Automatizadas
Antes de modificar cualquier archivo, verifica que tu entorno local pasa el 100% de las pruebas:
```bash
python tests/test_telemetry_65b.py
# O usando descubrimiento estándar de unittest:
python -m unittest discover tests
```
Debes observar `Ran 8 tests ... OK` con un 100% de tasa de éxito.

### 1.5 Paso 4: Iniciar la Estación Terrena
```bash
python main.py
```
Abre tu navegador en `http://localhost:8000`.

---

## 2. Estructura del Repositorio

```text
.
├── main.py                     # Motor principal (FastAPI + serial_asyncio + parser + persistencia)
├── arduino/
│   └── telemetry_simulator/    # Firmware de simulación de vuelo de 290s (C++/Arduino)
├── config/
│   ├── app.yaml                # Parámetros del puerto serie, HTTP/WebSocket y almacenamiento
│   └── frame.yaml              # Esquema declarativo de la trama LoRa de 65 bytes
├── data/                       # Registros locales de telemetría (ignorado en Git)
├── docs/                       # Documentación técnica completa (Inglés y Español)
│   ├── es/                     # Suite completa en Español
│   │   ├── api.md
│   │   ├── architecture.md
│   │   ├── future-calculations.md
│   │   ├── frame-schema.md
│   │   ├── frontend-dashboard.md
│   │   ├── getting-started.md
│   │   ├── packaging-exe.md
│   │   └── protocol.md
│   ├── api.md                  # Especificación en Inglés
│   ├── architecture.md
│   ├── frame-schema.md
│   └── ...
├── frontend/                   # Interfaz de usuario (HTML5 Canvas + Leaflet + CSS)
├── tests/
│   ├── __init__.py             # Marcador del paquete de pruebas
│   └── test_telemetry_65b.py   # Suite automatizada (parser, CRC, ventana deslizante, BD)
├── build_windows.bat           # Compilador de 1 clic para ejecutable de Windows
├── ground_station.spec         # Especificación PyInstaller
├── CONTRIBUTING.md             # Guía de contribución (Inglés)
├── CONTRIBUTING.es.md          # Esta guía en Español
├── README.md                   # Entrada principal (Inglés)
├── README.es.md                # Entrada principal (Español)
└── requirements.txt            # Dependencias Python
```

---

## 3. Flujo de Trabajo con Git y Estrategia de Ramas

1. **Rama Base:** Siempre bifurca tu trabajo a partir de la última versión de `main`:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/nombre-de-tu-mejora
   ```
2. **Convención de Nombres de Ramas:**
   - `feature/` para nuevas capacidades o instrumentos.
   - `fix/` para corrección de errores en decodificación o interfaz.
   - `docs/` para mejoras o adiciones en documentación.
   - `refactor/` para optimización de código sin alterar comportamiento externo.
3. **Mensajes de Commit Convencionales:**
   Usa el estándar Conventional Commits **en inglés**:
   - `feat(parser): add support for 24-bit signed integers`
   - `fix(buffer): handle consecutive false sync bytes correctly`
   - `docs(api): document new /api/history query parameters`
   - `test(serial): add streaming fragment reassembly test`

---

## 4. Estándares de Lenguaje y Documentación

- **Código:** Todo el código fuente en Python, JavaScript o C++, nombres de funciones, variables, comentarios de código y docstrings deben escribirse **estrictamente en inglés**.
- **Documentación:** La documentación técnica del repositorio se mantiene en **Inglés y Español**, con enlaces cruzados de selector de idioma en la parte superior de cada archivo.

---

## 5. Estilo de Código y Convenciones de Ingeniería

- **Python (3.11+):**
  - Cumplir estrictamente con PEP 8.
  - Usar anotaciones de tipo estáticas en todas las firmas de funciones (`def parse(self, frame: bytes) -> Optional[dict[str, Any]]:`).
  - No romper llamadas simples en múltiples líneas vacías innecesarias; mantener el código idiomático, legible y conciso.
  - Gestión limpia de recursos (`with open(...)`, conexiones cerradas en bloques `finally`).
- **JavaScript / Frontend:**
  - Código vanilla limpio sin frameworks pesados ni dependencias de compilación externas (cero bundlers, cero `npm`).
  - Renderizado por Canvas optimizado para $60\text{ FPS}$ mediante `requestAnimationFrame`.

---

## 6. Pruebas Automatizadas y Control de Calidad

Toda contribución debe validar:
1. **Ejecución local de pruebas:**
   ```bash
   python tests/test_telemetry_65b.py
   python -m unittest discover tests
   ```
2. **Integridad de enlaces en documentación:** Ningún enlace relativo roto en archivos Markdown.
3. **Compilación de sintaxis sin errores:**
   ```bash
   python -m py_compile main.py tests/test_telemetry_65b.py
   ```

---

## 7. Proceso de Pull Request (PR)

1. Sube tu rama a tu fork o repositorio remoto.
2. Abre un Pull Request contra la rama `main`.
3. Completa la descripción del PR explicando:
   - Problema resuelto o mejora introducida.
   - Pruebas ejecutadas y resultados obtenidos.
   - Cambios en documentación asociados.
4. El flujo de trabajo en GitHub Actions ejecutará automáticamente las pruebas antes de habilitar la fusión.
