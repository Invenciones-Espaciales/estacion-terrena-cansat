# Packaging the Ground Station as a Windows Executable (.exe)

This guide explains how to package the **Rocket Telemetry Ground Station** into a standalone Windows executable (`estacion-terrena.exe`) using **PyInstaller**.

---

## 1. Quick Option: Automated Build via GitHub Actions (Recommended)

If you are currently developing on Linux (such as a Raspberry Pi) and do not want to configure a Windows build machine:

1. Push your changes to GitHub:
   ```bash
   git push origin main
   ```
2. Navigate to your repository on GitHub and click on the **Actions** tab.
3. Select the **Build Windows Executable** workflow on the left sidebar.
4. Click **Run workflow** (or simply let it run automatically on push).
5. Once complete (approximately 1–2 minutes), download the **`estacion-terrena-windows`** ZIP artifact under the workflow run summary.
6. Extract the ZIP on your Windows PC and double-click `iniciar.bat` or `estacion-terrena.exe`.

---

## 2. Local Option: Building on a Windows PC

To build the executable directly on a Windows computer:

### Step 1: Install Python
Ensure Python 3.10 or higher is installed from [python.org](https://www.python.org/downloads/). During installation, make sure to check **"Add Python to PATH"**.

### Step 2: Run the 1-Click Build Script
In the root directory of the repository, double-click:
```cmd
build_windows.bat
```
Or run it from PowerShell / Command Prompt:
```cmd
.\build_windows.bat
```

This automated script will:
1. Create a clean build virtual environment (`.venv-build`).
2. Install all required runtime dependencies plus `pyinstaller`.
3. Bundle the application using the [`ground_station.spec`](../ground_station.spec) specification.
4. Package the executable along with `config/` and an empty `data/` directory into:
   * `dist\estacion-terrena-windows\`
   * `dist\estacion-terrena-windows.zip`

---

## 3. Manual Build Commands

If you prefer to run the commands manually:

```cmd
# Create virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install pyinstaller

# Build executable using spec file
pyinstaller --clean ground_station.spec
```

The resulting executable will be generated at `dist\estacion-terrena.exe`.

---

## 4. Running and Configuring on Windows

### Serial COM Port Configuration
On Windows, serial ports use the `COMx` naming convention (e.g. `COM3`, `COM5`, `COM7`).

1. Open **Device Manager** (`devmgmt.msc`) $\to$ **Ports (COM & LPT)** to find the COM port number assigned to your telemetry radio or microcontroller.
2. Edit `config\app.yaml` next to `estacion-terrena.exe`:
   ```yaml
   serial:
     port: "COM3"          # Change to your actual COM port
     baudrate: 115200
     reconnect_delay: 3

   websocket:
     host: "0.0.0.0"
     port: 8000

   storage:
     database: "data/telemetry.db"
     csv: "data/telemetry.csv"
   ```
3. Run `iniciar.bat` or `estacion-terrena.exe`.
4. Open [http://localhost:8000](http://localhost:8000) in your web browser.

---

## 5. Architectural Details of the Frozen Bundle

- **Static Assets & Config Fallbacks:** The web dashboard (`frontend/index.html`, CSS, images) and default frame YAML specifications are embedded directly inside the executable bundle and loaded via `sys._MEIPASS`.
- **External Configuration:** [`main.py`](../main.py) automatically checks for an external `config/` folder located next to the `.exe` first. If present, it uses the external configuration so you can modify COM ports or baud rates without recompiling.
- **Persistent Data:** SQLite databases and CSV logs are always written to the `data/` directory located adjacent to the `.exe`, ensuring mission logs are preserved permanently on disk.
