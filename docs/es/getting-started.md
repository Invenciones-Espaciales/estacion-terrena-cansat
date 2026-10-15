# Guía de Inicio Rápido y Manual de Operaciones

> **Idioma / Language:** [ 🇪🇸 Español ](getting-started.md) | [ 🇬🇧 English ](../getting-started.md)

---

## 1. Requisitos Previos

### 1.1 Requisitos de Software
- **Python:** Versión 3.10 o superior (Python 3.11+ recomendado).
- **Sistema Operativo:**
  - Linux (Debian, Ubuntu, Raspberry Pi OS, Arch, Fedora).
  - Windows 10/11 (x86_64).
  - macOS (Apple Silicon / Intel).
- **Navegador Web:** Cualquier navegador moderno con soporte para HTML5 Canvas y WebSockets (Chrome, Firefox, Edge, Safari).

### 1.2 Requisitos de Hardware
- Un receptor de estación terrena o puente USB a UART conectado a la computadora:
  - Puerto serie virtual USB CDC ACM (STM32, ESP32, Raspberry Pi Pico, Teensy).
  - Adaptadores USB UART estándar (FTDI FT232, Silicon Labs CP2102, WCH CH340).
  - Módems de telemetría LoRa (módulos SX1276/SX1278 con firmware transparente, radios SiK 433/915 MHz).

---

## 2. Permisos y Configuración del Puerto Serie

### 2.1 Permisos en Linux (`dialout` / `uucp`)
Por defecto, Linux restringe el acceso de lectura y escritura a los dispositivos serie (`/dev/ttyACM*` o `/dev/ttyUSB*`) al superusuario y al grupo `dialout` (o `uucp` en Arch).

1. Añadir el usuario actual al grupo `dialout`:
   ```bash
   sudo usermod -aG dialout $USER
   ```
2. Aplicar el cambio de permisos en la terminal activa:
   ```bash
   newgrp dialout
   ```
3. Identificar el dispositivo serie conectado:
   ```bash
   ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
   # O verificar en el registro del kernel:
   dmesg | grep -E "tty(ACM|USB)"
   ```

### 2.2 Puertos Serie en Windows
- Identificar el número de puerto en el **Administrador de Dispositivos** bajo **Puertos (COM y LPT)** (ej. `COM3`, `COM6`).
- Configurar el valor `port: "COMx"` en [`config/app.yaml`](../../config/app.yaml).
- `main.py` configura automáticamente `WindowsSelectorEventLoopPolicy` para garantizar estabilidad bajo Windows.

---

## 3. Instalación del Entorno

### 3.1 Crear y Activar el Entorno Virtual
```bash
# Crear entorno virtual
python3 -m venv .venv

# Activar en Linux / macOS:
source .venv/bin/activate

# Activar en Windows (PowerShell / CMD):
.venv\Scripts\activate
```

### 3.2 Instalar Dependencias
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Ejecución de la Estación Terrena

### 4.1 Iniciar el Servidor
```bash
python main.py
```

### 4.2 Acceso al Tablero Web
Abra el navegador en:
- **Tablero de Misión:** `http://localhost:8000`
- **Consola Pre-Vuelo Go/No-Go:** `http://localhost:8000/gonogo`
- **Consola de Recuperación:** `http://localhost:8000/recovery`

---

## 5. Pruebas sin Hardware Físico (Simulación Virtual)

Si no tiene el receptor físico conectado, puede simular el flujo de telemetría de dos maneras:

### Opción A: Par de Puertos Virtuales con `socat` (Linux)
```bash
# 1. Crear par de puertos serie virtuales conectados entre sí
socat -d -d pty,raw,echo=0,link=/tmp/ttyV0 pty,raw,echo=0,link=/tmp/ttyV1

# 2. Configurar en config/app.yaml:
#    serial:
#      port: "/tmp/ttyV0"

# 3. Enviar tramas generadas a /tmp/ttyV1 usando un script simulador
```

### Opción B: Ejecutar la Suite de Pruebas Automatizadas
```bash
# Ejecutar los 8 tests automatizados directamente
python tests/test_telemetry_65b.py

# O mediante descubrimiento estándar de unittest
python -m unittest discover tests
```

---

## 6. Documentación Relacionada

- **[Especificación del Protocolo Binario](protocol.md):** Mapa de memoria y tipos de datos.
- **[Guía de Contribución y Onboarding](../../CONTRIBUTING.es.md):** Flujo de trabajo en equipo.
- **[Compilación del Ejecutable de Windows](packaging-exe.md):** Generación de binarios sin consola.
