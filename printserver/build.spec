# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller build specification for IPP Print Server

This file configures PyInstaller to build a standalone executable
that includes all necessary dependencies and data files.

Usage:
    pyinstaller build.spec
    
Or for debugging:
    pyinstaller --debug=all build.spec
"""

import sys
import os
from pathlib import Path

# Get the directory containing this spec file
spec_dir = Path(SPECPATH)
project_root = spec_dir

# Application metadata
APP_NAME = 'printserver'
APP_VERSION = '1.0.0'
APP_DESCRIPTION = 'Universal IPP Print Server for Thermal Printers'
APP_AUTHOR = 'IPP Print Server Project'

# Build configuration
DEBUG = False
CONSOLE = True  # Set to False for windowed mode
ONE_FILE = True  # Set to False for one-directory mode

# Determine platform-specific settings
if sys.platform == 'win32':
    EXECUTABLE_NAME = f'{APP_NAME}.exe'
    ICON_FILE = None  # Add .ico file path if available
elif sys.platform == 'darwin':
    EXECUTABLE_NAME = APP_NAME
    ICON_FILE = None  # Add .icns file path if available  
else:
    EXECUTABLE_NAME = APP_NAME
    ICON_FILE = None

# Data files to include
datas = [
    # Include configuration files if any
    # (str(project_root / 'config' / 'default.conf'), 'config'),
]

# Hidden imports (modules that PyInstaller might miss)
hiddenimports = [
    # Core server modules
    'server.ipp_server',
    'server.ipp_parser', 
    'server.printer_backend',
    'server.converter',
    'server.mdns_announcer',
    'server.utils',
    'config.settings',
    'usb.usb_handler',
    
    # HTTP server dependencies
    'aiohttp.web',
    'aiohttp.web_request',
    'aiohttp.web_response',
    'aiohttp.hdrs',
    
    # mDNS dependencies
    'zeroconf',
    'zeroconf.asyncio',
    
    # USB dependencies
    'usb.core',
    'usb.util',
    'usb.backend',
    'usb.backend.libusb1',
    'usb.backend.openusb',
    'usb.backend.libusb0',
    
    # Image processing
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'PIL.ImageOps',
    
    # System and networking
    'socket',
    'asyncio',
    'threading',
    'subprocess',
    'platform',
    'logging',
    'logging.handlers',
    
    # Optional dependencies
    'psutil',
    'pypdf',
]

# Files and directories to exclude
excludes = [
    'tkinter',
    'matplotlib',
    'numpy',
    'scipy',
    'pandas',
    'jupyter',
    'IPython',
    'notebook',
    'sphinx',
    'pytest',
    'unittest',
    'test',
    'tests',
    '_pytest',
]

# Binary exclusions (reduce size)
binaries = []

# Hook directories
hookspath = []

# Additional paths for module search
pathex = [str(project_root)]

# Runtime hooks
runtime_hooks = []

# PyInstaller analysis
a = Analysis(
    ['main.py'],
    pathex=pathex,
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=hookspath,
    hooksconfig={},
    runtime_hooks=runtime_hooks,
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Remove duplicate files
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Build configuration
if ONE_FILE:
    # One-file mode: everything bundled into single executable
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name=EXECUTABLE_NAME,
        debug=DEBUG,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,  # Set to True to compress with UPX if available
        upx_exclude=[],
        runtime_tmpdir=None,
        console=CONSOLE,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON_FILE,
        version_file=None,  # Add version info file for Windows if needed
    )
else:
    # One-directory mode: executable with supporting files
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=EXECUTABLE_NAME,
        debug=DEBUG,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=CONSOLE,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON_FILE,
    )
    
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name=APP_NAME,
    )

# Platform-specific configurations
if sys.platform == 'darwin':
    # macOS app bundle
    app = BUNDLE(
        coll if not ONE_FILE else exe,
        name=f'{APP_NAME}.app',
        icon=ICON_FILE,
        bundle_identifier=f'com.ippserver.{APP_NAME}',
        version=APP_VERSION,
        info_plist={
            'CFBundleName': APP_NAME,
            'CFBundleDisplayName': APP_DESCRIPTION,
            'CFBundleVersion': APP_VERSION,
            'CFBundleShortVersionString': APP_VERSION,
            'NSHighResolutionCapable': True,
            'LSBackgroundOnly': False,
        },
    )