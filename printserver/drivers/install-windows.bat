@echo off
REM ############################################################################
REM ONE-POS Network Printer - Instalador Rápido para Windows
REM 
REM Este script instala automáticamente la impresora ONE-POS en Windows
REM 
REM Uso:
REM   install-windows.bat [IP_SERVIDOR] [PUERTO]
REM   
REM Ejemplo:
REM   install-windows.bat 192.168.1.100 631
REM   install-windows.bat (usa localhost:631 por defecto)
REM
REM ############################################################################

setlocal EnableDelayedExpansion

REM Configuración
set PRINTER_NAME=ONE-POS-Printer
set PRINTER_DESCRIPTION=ONE POS Network Printer
set PRINTER_LOCATION=Office

REM Parámetros (con valores por defecto)
if "%~1"=="" (
    set SERVER_IP=localhost
) else (
    set SERVER_IP=%~1
)

if "%~2"=="" (
    set SERVER_PORT=631
) else (
    set SERVER_PORT=%~2
)

set PRINTER_URL=http://!SERVER_IP!:!SERVER_PORT!/ipp/printer

REM ############################################################################
REM Banner
REM ############################################################################

cls
echo.
echo ========================================================
echo.
echo        ONE-POS Network Printer Installer
echo                   Windows
echo.
echo ========================================================
echo.

REM ############################################################################
REM Verificar permisos de administrador
REM ############################################################################

net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo [ERROR] Este script debe ejecutarse como Administrador
    echo.
    echo Haz clic derecho en el archivo y selecciona:
    echo "Ejecutar como administrador"
    echo.
    pause
    exit /b 1
)

echo [OK] Permisos de administrador verificados
echo.

REM ############################################################################
REM Información de instalación
REM ############################################################################

echo Parametros de instalacion:
echo   Servidor: !SERVER_IP!
echo   Puerto: !SERVER_PORT!
echo   URL: !PRINTER_URL!
echo.

REM ############################################################################
REM Eliminar impresora existente (si existe)
REM ############################################################################

echo Verificando si la impresora ya existe...
powershell -Command "Get-Printer -Name '%PRINTER_NAME%' -ErrorAction SilentlyContinue" >nul 2>&1

if !errorLevel! EQU 0 (
    echo [WARNING] La impresora '%PRINTER_NAME%' ya existe. Eliminando...
    powershell -Command "Remove-Printer -Name '%PRINTER_NAME%' -Confirm:$false"
    echo [OK] Impresora anterior eliminada
) else (
    echo [OK] No hay conflictos
)
echo.

REM ############################################################################
REM Instalar impresora IPP
REM ############################################################################

echo Instalando impresora...
echo.

REM Windows 10/11 soporta IPP nativamente
REM Usar Add-Printer con puerto IPP

powershell -Command ^
    "$printerName = '%PRINTER_NAME%'; ^
     $printerUrl = '!PRINTER_URL!'; ^
     $description = '%PRINTER_DESCRIPTION%'; ^
     $location = '%PRINTER_LOCATION%'; ^
     try { ^
         Add-PrinterPort -Name 'IPP_!SERVER_IP!_!SERVER_PORT!' -PrinterHostAddress '!PRINTER_URL!' -ErrorAction Stop; ^
         Write-Host '[OK] Puerto IPP creado' -ForegroundColor Green; ^
     } catch { ^
         Write-Host '[INFO] Puerto IPP ya existe o no se pudo crear' -ForegroundColor Yellow; ^
     }; ^
     try { ^
         Add-Printer -Name $printerName -DriverName 'Microsoft IPP Class Driver' -PortName 'IPP_!SERVER_IP!_!SERVER_PORT!' -Location $location -Comment $description -ErrorAction Stop; ^
         Write-Host '[OK] Impresora instalada correctamente' -ForegroundColor Green; ^
     } catch { ^
         Write-Host '[ERROR] No se pudo instalar la impresora' -ForegroundColor Red; ^
         Write-Host 'Intentando con metodo alternativo...' -ForegroundColor Yellow; ^
         rundll32 printui.dll,PrintUIEntry /if /b '$printerName' /f '%windir%\inf\ntprint.inf' /r '!PRINTER_URL!' /m 'Generic / Text Only'; ^
     }"

if !errorLevel! NEQ 0 (
    echo.
    echo [ERROR] Error al instalar la impresora
    echo.
    echo Intentando metodo manual...
    echo Por favor, espera...
    
    REM Método alternativo: usar rundll32
    rundll32 printui.dll,PrintUIEntry /if /b "%PRINTER_NAME%" /f "%windir%\inf\ntprint.inf" /r "!PRINTER_URL!" /m "Generic / Text Only"
)

echo.

REM ############################################################################
REM Verificar instalación
REM ############################################################################

echo Verificando instalacion...
powershell -Command "Get-Printer -Name '%PRINTER_NAME%' -ErrorAction SilentlyContinue" >nul 2>&1

if !errorLevel! EQU 0 (
    echo [OK] Impresora instalada y lista
    echo.
    
    REM Preguntar si establecer como predeterminada
    set /p SET_DEFAULT="Establecer como impresora predeterminada? (S/N): "
    if /i "!SET_DEFAULT!"=="S" (
        powershell -Command "Set-Printer -Name '%PRINTER_NAME%' -Default"
        echo [OK] Impresora establecida como predeterminada
    )
    
    echo.
    echo ========================================================
    echo.
    echo           INSTALACION COMPLETADA EXITOSAMENTE
    echo.
    echo ========================================================
    echo.
    echo Informacion de la impresora:
    echo   Nombre: %PRINTER_NAME%
    echo   URL: !PRINTER_URL!
    echo.
    echo La impresora esta lista para usar desde cualquier aplicacion.
    echo.
    echo Para imprimir una pagina de prueba:
    echo   1. Abrir Panel de Control ^> Dispositivos e Impresoras
    echo   2. Hacer clic derecho en "%PRINTER_NAME%"
    echo   3. Seleccionar "Propiedades de impresora"
    echo   4. Clic en "Imprimir pagina de prueba"
    echo.
) else (
    echo.
    echo [ERROR] La impresora no se pudo instalar correctamente
    echo.
    echo Por favor, intenta instalarla manualmente:
    echo   1. Abrir Panel de Control ^> Dispositivos e Impresoras
    echo   2. Clic en "Agregar una impresora"
    echo   3. Seleccionar "Agregar impresora de red, inalambrica o Bluetooth"
    echo   4. Seleccionar "La impresora que deseo no esta en la lista"
    echo   5. Seleccionar "Agregar una impresora usando direccion TCP/IP o nombre de host"
    echo   6. Ingresar: !PRINTER_URL!
    echo.
)

pause
