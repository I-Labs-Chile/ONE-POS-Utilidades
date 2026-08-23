# -*- mode: python ; coding: utf-8 -*-
# Spec PyInstaller para Linux. Ejecutar desde build/:
#   ../.venv/bin/pyinstaller --clean --noconfirm escpos-linux.spec
# La versión se lee de pyproject.toml para nombrar el paquete.

block_cipher = None

a = Analysis(
    ['../run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../app', 'app'),
    ],
    hiddenimports=[
        'app',
        'app.web',
        'app.web.api',
        'app.web.frontend',
        'app.core',
        'app.core.test_print',
        'onepos_common',
        'onepos_common.queue',
        'onepos_common.worker',
        'onepos_common.status',
        'onepos_common.escpos',
        'onepos_common.image',
        'onepos_common.network',
        'onepos_common.printer_manager',
        'onepos_common.usb_printer',
        'onepos_common.usb_detector',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'usb.backend',
        'usb.backend.libusb1',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='escpos-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
