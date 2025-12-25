@echo off
REM Script de empaquetado para Windows
REM Genera un ejecutable standalone con PyInstaller

setlocal enabledelayedexpansion

echo ==========================================
echo ONE-POS Utilidades - Build para Windows
echo ==========================================
echo.

REM Directorio base del proyecto
set "PROJECT_DIR=%~dp0.."
set "BUILD_DIR=%~dp0"
set "DIST_DIR=%BUILD_DIR%dist"
set "OUTPUT_DIR=%BUILD_DIR%output"

echo Directorio del proyecto: %PROJECT_DIR%
echo.

REM Verificar que estamos en el directorio correcto
if not exist "%PROJECT_DIR%\run.py" (
    echo Error: No se encuentra run.py
    echo Ejecuta este script desde la carpeta build\
    exit /b 1
)

REM Limpiar builds anteriores
echo Limpiando builds anteriores...
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%BUILD_DIR%\build_temp" rmdir /s /q "%BUILD_DIR%\build_temp"
if exist "%BUILD_DIR%\*.spec" del /q "%BUILD_DIR%\*.spec"
if exist "%OUTPUT_DIR%" rmdir /s /q "%OUTPUT_DIR%"
mkdir "%OUTPUT_DIR%"

REM Verificar Python y entorno virtual
if not exist "%PROJECT_DIR%\.venv\Scripts\python.exe" (
    echo Error: No se encuentra el entorno virtual en .venv
    echo Crea el entorno virtual primero: python -m venv .venv
    exit /b 1
)

REM Verificar/instalar PyInstaller
echo Verificando PyInstaller...
"%PROJECT_DIR%\.venv\Scripts\python.exe" -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Instalando PyInstaller...
    "%PROJECT_DIR%\.venv\Scripts\pip.exe" install pyinstaller
)

REM Versión
set "VERSION=1.0.0"
set "APP_NAME=escpos-server-windows-x64-v%VERSION%"

echo Version: %VERSION%
echo Nombre del paquete: %APP_NAME%
echo.

REM Crear spec file personalizado
echo Generando configuracion de PyInstaller...
(
echo # -*- mode: python ; coding: utf-8 -*-
echo.
echo block_cipher = None
echo.
echo a = Analysis^(
echo     ['..\\run.py'],
echo     pathex=[],
echo     binaries=[],
echo     datas=[
echo         ^('..\\app', 'app'^),
echo     ],
echo     hiddenimports=[
echo         'app',
echo         'app.web',
echo         'app.web.api',
echo         'app.web.frontend',
echo         'app.core',
echo         'app.core.worker',
echo         'app.core.queue',
echo         'app.core.test_print',
echo         'app.utils',
echo         'app.utils.escpos',
echo         'app.utils.image',
echo         'app.utils.network',
echo         'app.utils.usb_printer',
echo         'app.utils.usb_detector',
echo         'uvicorn.logging',
echo         'uvicorn.loops',
echo         'uvicorn.loops.auto',
echo         'uvicorn.protocols',
echo         'uvicorn.protocols.http',
echo         'uvicorn.protocols.http.auto',
echo         'uvicorn.protocols.websockets',
echo         'uvicorn.protocols.websockets.auto',
echo         'uvicorn.lifespan',
echo         'uvicorn.lifespan.on',
echo         'usb.backend',
echo         'usb.backend.libusb1',
echo     ],
echo     hookspath=[],
echo     hooksconfig={},
echo     runtime_hooks=[],
echo     excludes=[],
echo     win_no_prefer_redirects=False,
echo     win_private_assemblies=False,
echo     cipher=block_cipher,
echo     noarchive=False,
echo ^)
echo.
echo pyz = PYZ^(a.pure, a.zipped_data, cipher=block_cipher^)
echo.
echo exe = EXE^(
echo     pyz,
echo     a.scripts,
echo     a.binaries,
echo     a.zipfiles,
echo     a.datas,
echo     [],
echo     name='escpos-server',
echo     debug=False,
echo     bootloader_ignore_signals=False,
echo     strip=False,
echo     upx=True,
echo     upx_exclude=[],
echo     runtime_tmpdir=None,
echo     console=True,
echo     disable_windowed_traceback=False,
echo     argv_emulation=False,
echo     target_arch=None,
echo     codesign_identity=None,
echo     entitlements_file=None,
echo     icon=None,
echo ^)
) > "%BUILD_DIR%\escpos-windows.spec"

REM Compilar con PyInstaller
echo Compilando aplicacion...
cd /d "%BUILD_DIR%"
"%PROJECT_DIR%\.venv\Scripts\pyinstaller.exe" --clean escpos-windows.spec

REM Verificar que se creó el ejecutable
if not exist "%DIST_DIR%\escpos-server.exe" (
    echo Error: No se genero el ejecutable
    exit /b 1
)

echo [OK] Ejecutable generado correctamente
echo.

REM Crear estructura del release
echo Creando paquete de distribucion...
set "RELEASE_DIR=%OUTPUT_DIR%\%APP_NAME%"
mkdir "%RELEASE_DIR%"

REM Copiar ejecutable
copy "%DIST_DIR%\escpos-server.exe" "%RELEASE_DIR%\"

REM Crear directorio de datos
mkdir "%RELEASE_DIR%\data"

REM Crear archivo de configuración de ejemplo
(
echo # Configuracion de la impresora
echo PRINTER_IF=usb
echo # PRINTER_IF=tcp
echo.
echo # Para impresoras TCP
echo # PRINTER_HOST=192.168.1.100
echo # PRINTER_PORT=9100
echo.
echo # Para impresoras USB especificas ^(autodeteccion si se omite^)
echo # USB_VENDOR=0x04b8
echo # USB_PRODUCT=0x0202
echo.
echo # Configuracion del papel
echo PAPER_WIDTH_PX=384
echo # PAPER_WIDTH_PX=576  # Para papel de 80mm
echo.
echo # Puerto del servidor
echo SERVER_PORT=8080
echo.
echo # Directorio de datos
echo QUEUE_DIR=./data
) > "%RELEASE_DIR%\.env.example"

REM Crear README de distribución
(
echo ONE-POS Utilidades - Servidor de Impresion ESC/POS para Windows
echo ================================================================
echo.
echo INSTALACION
echo -----------
echo.
echo 1. Descomprimir el archivo ZIP en una carpeta de tu eleccion
echo.
echo 2. Configurar la aplicacion:
echo    - Copiar .env.example a .env
echo    - Editar .env con tu configuracion
echo.
echo EJECUCION
echo ---------
echo.
echo Ejecutar directamente:
echo.
echo     escpos-server.exe
echo.
echo ACCESO
echo ------
echo.
echo Una vez iniciado, abre tu navegador en:
echo.
echo     http://localhost:8080
echo.
echo O usa la IP local del servidor desde otro dispositivo.
echo.
echo SERVICIO DE WINDOWS ^(OPCIONAL^)
echo ------------------------------
echo.
echo Para ejecutar como servicio de Windows, puedes usar NSSM:
echo.
echo 1. Descargar NSSM: https://nssm.cc/download
echo.
echo 2. Instalar el servicio:
echo    nssm install EscposServer "C:\ruta\completa\escpos-server.exe"
echo.
echo 3. Configurar y arrancar:
echo    nssm start EscposServer
echo.
echo NOTAS IMPORTANTES
echo ----------------
echo.
echo - Windows Defender puede bloquear el ejecutable la primera vez
echo - Agrega una excepcion en Windows Defender si es necesario
echo - Para impresoras USB, asegurate de tener los drivers instalados
echo.
echo SOPORTE
echo -------
echo.
echo GitHub: https://github.com/I-Labs-Chile/ONE-POS-Utilidades
) > "%RELEASE_DIR%\README.txt"

REM Copiar licencia
if exist "%PROJECT_DIR%\LICENSE" copy "%PROJECT_DIR%\LICENSE" "%RELEASE_DIR%\"

REM Crear ZIP
echo Comprimiendo paquete...
cd /d "%OUTPUT_DIR%"
powershell -command "Compress-Archive -Path '%APP_NAME%' -DestinationPath '%APP_NAME%.zip' -Force"

REM Información final
echo.
echo ==========================================
echo Build completado exitosamente
echo ==========================================
echo.
echo Ejecutable: %RELEASE_DIR%\escpos-server.exe
echo Paquete: %OUTPUT_DIR%\%APP_NAME%.zip
echo.
echo Para probar:
echo   cd %RELEASE_DIR%
echo   escpos-server.exe
echo.

pause
