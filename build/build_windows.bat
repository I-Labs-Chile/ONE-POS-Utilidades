@echo off
REM Build de release para Windows x64.
REM Uso: build\build_windows.bat [servidor^|cabina^|ambos]   (default: ambos)
REM Opcional: set POPPLER_DIR=c:\ruta\con\pdftoppm.exe para incluir Poppler
REM           en el release del servidor (necesario para imprimir PDF).

setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0.."
set "BUILD_DIR=%~dp0"
set "DIST_DIR=%BUILD_DIR%dist"
set "OUTPUT_DIR=%BUILD_DIR%output"

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=ambos"
if /i not "%TARGET%"=="servidor" if /i not "%TARGET%"=="cabina" if /i not "%TARGET%"=="ambos" (
    echo Error: target invalido "%TARGET%" ^(usa: servidor, cabina o ambos^)
    exit /b 1
)

if not exist "%PROJECT_DIR%\run.py" (
    echo Error: no se encuentra run.py
    exit /b 1
)
if /i not "%TARGET%"=="servidor" if not exist "%PROJECT_DIR%\run_cabina.py" (
    echo Error: no se encuentra run_cabina.py
    exit /b 1
)
if not exist "%PROJECT_DIR%\.venv\Scripts\python.exe" (
    echo Error: no existe .venv ^(crea el entorno e instala requirements.txt^)
    exit /b 1
)

REM Version unica fuente de verdad: pyproject.toml
set "VERSION="
for /f "usebackq tokens=2 delims== " %%v in (`findstr /b "version" "%PROJECT_DIR%\pyproject.toml"`) do set "VERSION=%%~v"
if not defined VERSION set "VERSION=0.0.0"

echo ==^> ONE-POS Utilidades %VERSION% ^(Windows^) - target: %TARGET%

"%PROJECT_DIR%\.venv\Scripts\python.exe" -c "import PyInstaller" 2>nul || (
    echo ==^> Instalando PyInstaller...
    "%PROJECT_DIR%\.venv\Scripts\pip.exe" install pyinstaller
)

if exist "%OUTPUT_DIR%" rmdir /s /q "%OUTPUT_DIR%"
mkdir "%OUTPUT_DIR%"

if /i "%TARGET%"=="servidor" goto build_servidor
if /i "%TARGET%"=="cabina" goto build_cabina

:build_servidor
call :build_target servidor || goto :fail
if /i "%TARGET%"=="ambos" goto build_cabina
goto :ok

:build_cabina
call :build_target cabina || goto :fail
goto :ok

:build_target
setlocal enabledelayedexpansion
set "TGT=%~1"
if /i "%TGT%"=="servidor" (
    set "SPEC=escpos-windows.spec"
    set "EXE_NAME=escpos-server"
    set "APP_NAME=escpos-server-windows-x64-v%VERSION%"
) else (
    set "SPEC=escpos-cabina-windows.spec"
    set "EXE_NAME=escpos-cabina"
    set "APP_NAME=escpos-cabina-windows-x64-v%VERSION%"
)

echo ==^> Compilando !TGT! ^(!SPEC!^)...
cd /d "%BUILD_DIR%"
"%PROJECT_DIR%\.venv\Scripts\pyinstaller.exe" --clean --noconfirm "!SPEC!"
if errorlevel 1 (endlocal & exit /b 1)

if not exist "%DIST_DIR%\!EXE_NAME!.exe" (
    echo Error: no se genero el ejecutable !EXE_NAME!.exe
    endlocal & exit /b 1
)

echo ==^> Armando paquete de !TGT!...
set "RELEASE_DIR=%OUTPUT_DIR%\!APP_NAME!"
mkdir "%RELEASE_DIR%\data"
copy "%DIST_DIR%\!EXE_NAME!.exe" "%RELEASE_DIR%\" >nul
copy "%PROJECT_DIR%\LICENSE" "%RELEASE_DIR%\" >nul

set "POPPLER_NOTE="
if /i "%TGT%"=="servidor" (
    copy "%BUILD_DIR%launch-server-windows.ps1" "%RELEASE_DIR%\" >nul
    copy "%PROJECT_DIR%\.env.example" "%RELEASE_DIR%\" >nul
    (
        echo SERVIDOR DE IMPRESION ESC/POS - INICIO RAPIDO
        echo =============================================
        echo 1^) Ejecutar escpos-server.exe ^(si Windows lo bloquea: click derecho,
        echo    Propiedades y marcar "Desbloquear"^).
        echo 2^) Abrir http://localhost:8080 y arrastrar PDF o imagenes.
        echo.
        echo Configuracion opcional: copiar .env.example a .env y editar.
        echo Guia completa: https://github.com/I-Labs-Chile/ONE-POS-Utilidades/tree/main/docs
    ) > "%RELEASE_DIR%\LEEME.txt"
    REM Poppler opcional para imprimir PDF
    if defined POPPLER_DIR if exist "%POPPLER_DIR%\pdftoppm.exe" (
        copy "%POPPLER_DIR%\pdftoppm.exe" "%RELEASE_DIR%\" >nul
        copy "%POPPLER_DIR%\*.dll" "%RELEASE_DIR%\" >nul 2>&1
        echo Incluye Poppler: se pueden imprimir PDF.>> "%RELEASE_DIR%\LEEME.txt"
        set "POPPLER_NOTE=si"
    )
    if not defined POPPLER_NOTE (
        echo NOTA: sin Poppler ^(pdftoppm.exe^) solo se imprimen imagenes, no PDF.>> "%RELEASE_DIR%\LEEME.txt"
    )
) else (
    copy "%BUILD_DIR%launch-cabina-windows.ps1" "%RELEASE_DIR%\" >nul
    copy "%PROJECT_DIR%\cabina\.env.example" "%RELEASE_DIR%\" >nul
    (
        echo CABINA FOTOGRAFICA ONE-POS - INICIO RAPIDO
        echo ==========================================
        echo 1^) Ejecutar escpos-cabina.exe ^(instala el driver de la impresora antes^).
        echo 2^) Abrir http://localhost:8081 en Chrome/Edge y permitir la camara.
        echo 3^) Espacio/F foto | Enter/A imprimir | Esc/R repetir.
        echo.
        echo Requiere impresora instalada en Windows. La autodeteccion busca
        echo impresoras tipo POS-58/POS-80/Thermal y usa la primera disponible.
        echo Configuracion opcional: copiar .env.example a .env y editar.
        echo Guia completa: https://github.com/I-Labs-Chile/ONE-POS-Utilidades/tree/main/docs
    ) > "%RELEASE_DIR%\LEEME.txt"
)

cd /d "%OUTPUT_DIR%"
powershell -NoProfile -Command "Compress-Archive -Path '!APP_NAME!' -DestinationPath '!APP_NAME!.zip' -Force"
endlocal
exit /b 0

:ok
echo ==^> Listo:
dir /b "%OUTPUT_DIR%\*.zip"
if not defined CI pause
exit /b 0

:fail
echo ==^> Build FALLIDO
if not defined CI pause
exit /b 1
