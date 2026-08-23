# -*- mode: python ; coding: utf-8 -*-
# Spec PyInstaller para la Cabina Fotográfica en Windows.
# Ejecutar desde build\:  ..\.venv\Scripts\pyinstaller.exe --clean --noconfirm escpos-cabina-windows.spec
# Empaqueta SOLO cabina/ + onepos_common/ (nunca app/). Impresión vía spooler RAW.

block_cipher = None

a = Analysis(
    ['..\\run_cabina.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('..\\cabina', 'cabina'),
    ],
    hiddenimports=[
        'cabina',
        'cabina.api',
        'cabina.compose',
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
        'qrcode',
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
        'app',
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
    name='escpos-cabina',
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
