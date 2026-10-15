# Compilación de la Estación Terrena como Ejecutable para Windows (.exe)

> **Idioma / Language:** [ 🇪🇸 Español ](packaging-exe.md) | [ 🇬🇧 English ](../packaging-exe.md)

---

## 1. Opción Rápida: Compilación Automatizada en la Nube con GitHub Actions

Si está desarrollando en Linux (ej. Raspberry Pi o servidor) y no desea configurar un entorno de compilación en Windows:

1. Suba los cambios a su repositorio:
   ```bash
   git push origin main
   ```
2. Abra el repositorio en GitHub y haga clic en la pestaña **Actions**.
3. Seleccione el flujo de trabajo **Build Windows Executable** en la barra lateral izquierda.
4. El flujo ejecutará automáticamente la suite de pruebas (`python -m unittest discover tests`) y compilará el ejecutable en un ejecutor nativo de Windows.
5. Al finalizar (aprox. 1 a 2 minutos), descargue el artefacto ZIP **`estacion-terrena-windows`** en el resumen de la ejecución.
6. Descomprima el archivo ZIP en su computadora con Windows y haga doble clic en `iniciar.bat` o `estacion-terrena.exe`.

---

## 2. Opción Local: Compilar en una Computadora con Windows

Para compilar el binario directamente en una máquina Windows:

### Paso 1: Instalar Python
Asegúrese de tener instalado Python 3.10 o superior desde [python.org](https://www.python.org/downloads/). Durante el instalador, active la casilla obligatoria **"Add Python to PATH"**.

### Paso 2: Ejecutar el Script Automatizado de 1 Clic
En el directorio raíz del repositorio, haga doble clic en:
```cmd
build_windows.bat
```
O ejecútelo desde PowerShell o Símbolo del sistema (CMD):
```cmd
.\build_windows.bat
```

Este script automatizado realiza los siguientes pasos de forma transparente:
1. Crea un entorno virtual de compilación limpio (`.venv-build`).
2. Instala las dependencias del proyecto (`requirements.txt`) y `pyinstaller`.
3. Ejecuta la suite de pruebas automatizadas (`python -m unittest discover tests`) para asegurar que no se compilen binarios defectuosos.
4. Compila el ejecutable independiente utilizando el archivo de especificación [`ground_station.spec`](../../ground_station.spec).
5. Empaqueta el ejecutable junto con la carpeta de configuraciones `config/` y una carpeta `data/` limpia en:
   - `dist\estacion-terrena-windows\`
   - `dist\estacion-terrena-windows.zip`

---

## 3. Comandos Manuales de Compilación

Si prefiere compilar paso a paso en su propia terminal:

```cmd
# 1. Crear y activar entorno virtual
python -m venv .venv
.\.venv\Scripts\activate

# 2. Instalar dependencias y PyInstaller
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# 3. Validar tests
python -m unittest discover tests

# 4. Compilar con PyInstaller
pyinstaller --clean ground_station.spec
```

---

## 4. Estructura de la Distribución Generada

La carpeta lista para usar (`dist\estacion-terrena-windows\`) contiene:

```text
estacion-terrena-windows/
├── estacion-terrena.exe    # Binario ejecutable compilado con servidor web y FastAPI
├── iniciar.bat             # Acceso directo para iniciar y abrir el navegador en localhost:8000
├── config/
│   ├── app.yaml            # Configuración del puerto serie COMx y red
│   └── frame.yaml          # Esquema de trama de 65 bytes
└── data/                   # Carpeta donde se crearán telemetry.db y telemetry.csv
```

---

## 5. Documentación Relacionada

- **[Guía de Inicio Rápido](getting-started.md):** Manual de puesta en marcha.
- **[Especificación de la API](api.md):** Endpoints HTTP y WebSocket provistos por el ejecutable.
