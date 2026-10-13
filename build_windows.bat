@echo off
setlocal enabledelayedexpansion

echo ====================================================================
echo  Rocket Telemetry Ground Station - Windows Executable Builder
echo ====================================================================
echo.

:: 1. Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH.
    echo Please install Python 3.10+ from https://python.org and check "Add Python to PATH".
    pause
    exit /b 1
)

echo [1/5] Setting up build environment...
if not exist ".venv-build" (
    echo Creating virtual environment for building...
    python -m venv .venv-build
)

call .venv-build\Scripts\activate.bat

echo [2/5] Installing project dependencies and PyInstaller...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo [3/5] Compiling executable with PyInstaller...
pyinstaller --clean ground_station.spec

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] PyInstaller compilation failed! Check logs above.
    pause
    exit /b 1
)

echo [4/5] Preparing distribution package...
set DIST_DIR=dist\estacion-terrena-windows
if exist "%DIST_DIR%" rd /s /q "%DIST_DIR%"
mkdir "%DIST_DIR%"
mkdir "%DIST_DIR%\config"
mkdir "%DIST_DIR%\data"

copy "dist\estacion-terrena.exe" "%DIST_DIR%\" >nul
copy "config\app.yaml" "%DIST_DIR%\config\" >nul
copy "config\frame.yaml" "%DIST_DIR%\config\" >nul

:: Create launcher script for convenience
(
    echo @echo off
    echo title Estacion Terrena Telemetria
    echo echo Starting Ground Station...
    echo echo Open http://localhost:8000 in your browser.
    echo estacion-terrena.exe
    echo pause
) > "%DIST_DIR%\iniciar.bat"

:: Create release ZIP archive if powershell is available
echo [5/5] Creating ZIP release package...
powershell -Command "Compress-Archive -Path '%DIST_DIR%' -DestinationPath 'dist\estacion-terrena-windows.zip' -Force" 2>nul

echo.
echo ====================================================================
echo  BUILD SUCCESSFUL!
echo ====================================================================
echo.
echo Standalone executable: %DIST_DIR%\estacion-terrena.exe
echo Distribution folder:   %DIST_DIR%\
echo Distribution zip:      dist\estacion-terrena-windows.zip
echo.
echo To configure the serial COM port:
echo   Edit %DIST_DIR%\config\app.yaml (e.g. set port: "COM3")
echo.
pause
