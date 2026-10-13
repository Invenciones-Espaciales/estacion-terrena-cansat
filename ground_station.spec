# -*- mode: python ; coding: utf-8 -*-
# PyInstaller specification file for Rocket Telemetry Ground Station

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Collect all dynamic uvicorn and serial_asyncio submodules
hidden_imports = [
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "fastapi",
    "starlette",
    "starlette.routing",
    "starlette.staticfiles",
    "starlette.responses",
    "starlette.types",
    "serial",
    "serial.tools",
    "serial.tools.list_ports",
    "serial_asyncio",
    "yaml",
    "sqlite3",
    "csv",
    "json",
    "asyncio",
]

# Additional hidden imports from uvicorn package
hidden_imports += collect_submodules("uvicorn")
hidden_imports += collect_submodules("fastapi")
hidden_imports += collect_submodules("starlette")

# Bundled data directories (frontend templates/assets and default configs)
datas = [
    ("config", "config"),
    ("frontend", "frontend"),
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "notebook", "pandas"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="estacion-terrena",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Kept True to display console logs and serial diagnostics
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Path to icon.ico if provided
)
