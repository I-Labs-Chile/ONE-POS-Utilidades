# -*- mode: python ; coding: utf-8 -*-
# Spec PyInstaller para Windows. Ejecutar desde build\:
#   ..\.venv\Scripts\pyinstaller.exe --clean --noconfirm escpos-windows.spec
# Excluye los backends USB (PyUSB/libusb) y win32print entra como hiddenimport:
# en Windows la impresión va por el spooler (RAW), no por /dev ni libusb.

block_cipher = None

a = Analysis(
    ['..\\run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('..\\app', 'app'),
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
        'onepos_common.windows_spooler',
        'win32print',
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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'usb',
        'usb.backend',
        'usb.backend.libusb1',
        'onepos_common.usb_printer',
        'onepos_common.usb_detector',
        'tkinter',
    ],
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
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
