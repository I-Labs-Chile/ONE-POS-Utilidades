# ############################################################################
# ONE-POS Network Printer - Instalador Rápido para Windows (PowerShell)
# 
# Este script instala automáticamente la impresora ONE-POS en Windows
# 
# Uso:
#   .\install-windows.ps1 [-ServerIP "192.168.1.100"] [-ServerPort 631]
#   
# Ejemplo:
#   .\install-windows.ps1 -ServerIP "192.168.1.100" -ServerPort 631
#   .\install-windows.ps1  # Usa localhost:631 por defecto
#
# ############################################################################

param(
    [string]$ServerIP = "localhost",
    [int]$ServerPort = 631,
    [switch]$SetDefault = $false
)

# Configuración
$PrinterName = "ONE-POS-Printer"
$PrinterDescription = "ONE POS Network Printer"
$PrinterLocation = "Office"
$PrinterURL = "http://${ServerIP}:${ServerPort}/ipp/printer"
$PortName = "IPP_${ServerIP}_${ServerPort}"

# ############################################################################
# Funciones auxiliares
# ############################################################################

function Write-Banner {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "       ONE-POS Network Printer Installer" -ForegroundColor Cyan
    Write-Host "                  Windows" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Remove-ExistingPrinter {
    Write-Host "🔍 Verificando si la impresora ya existe..." -ForegroundColor Blue
    
    $existingPrinter = Get-Printer -Name $PrinterName -ErrorAction SilentlyContinue
    
    if ($existingPrinter) {
        Write-Host "⚠️  La impresora '$PrinterName' ya existe. Eliminando..." -ForegroundColor Yellow
        Remove-Printer -Name $PrinterName -Confirm:$false
        Write-Host "✅ Impresora anterior eliminada" -ForegroundColor Green
    } else {
        Write-Host "✅ No hay conflictos" -ForegroundColor Green
    }
    Write-Host ""
}

function Add-IPPPort {
    Write-Host "📡 Creando puerto IPP..." -ForegroundColor Blue
    
    try {
        # Verificar si el puerto ya existe
        $existingPort = Get-PrinterPort -Name $PortName -ErrorAction SilentlyContinue
        
        if ($existingPort) {
            Write-Host "ℹ️  Puerto IPP ya existe" -ForegroundColor Cyan
        } else {
            # Crear puerto IPP
            Add-PrinterPort -Name $PortName -PrinterHostAddress $PrinterURL -ErrorAction Stop
            Write-Host "✅ Puerto IPP creado: $PortName" -ForegroundColor Green
        }
        return $true
    } catch {
        Write-Host "⚠️  No se pudo crear puerto IPP: $_" -ForegroundColor Yellow
        return $false
    }
    Write-Host ""
}

function Install-Printer {
    Write-Host "📥 Instalando impresora..." -ForegroundColor Blue
    Write-Host ""
    Write-Host "  Nombre: $PrinterName" -ForegroundColor White
    Write-Host "  URL: $PrinterURL" -ForegroundColor White
    Write-Host "  Descripción: $PrinterDescription" -ForegroundColor White
    Write-Host "  Ubicación: $PrinterLocation" -ForegroundColor White
    Write-Host ""
    
    try {
        # Intentar con driver IPP de Microsoft (Windows 10/11)
        $drivers = @(
            "Microsoft IPP Class Driver",
            "Microsoft Print To PDF",
            "Generic / Text Only"
        )
        
        $success = $false
        foreach ($driver in $drivers) {
            try {
                Write-Host "  Intentando con driver: $driver" -ForegroundColor Gray
                
                Add-Printer -Name $PrinterName `
                    -DriverName $driver `
                    -PortName $PortName `
                    -Location $PrinterLocation `
                    -Comment $PrinterDescription `
                    -ErrorAction Stop
                
                Write-Host "✅ Impresora instalada con driver: $driver" -ForegroundColor Green
                $success = $true
                break
            } catch {
                Write-Host "  ⚠️  No funciona con $driver" -ForegroundColor DarkYellow
            }
        }
        
        if (-not $success) {
            throw "No se pudo instalar con ningún driver disponible"
        }
        
        return $true
    } catch {
        Write-Host "❌ Error al instalar la impresora: $_" -ForegroundColor Red
        return $false
    }
    Write-Host ""
}

function Set-DefaultPrinter {
    param([bool]$Force = $false)
    
    if ($Force -or $SetDefault) {
        try {
            $printer = Get-Printer -Name $PrinterName -ErrorAction Stop
            # Windows PowerShell way
            (New-Object -ComObject WScript.Network).SetDefaultPrinter($PrinterName)
            Write-Host "✅ Impresora establecida como predeterminada" -ForegroundColor Green
        } catch {
            Write-Host "⚠️  No se pudo establecer como predeterminada" -ForegroundColor Yellow
        }
    } else {
        $response = Read-Host "¿Establecer como impresora predeterminada? (S/N)"
        if ($response -match '^[Ss]$') {
            try {
                (New-Object -ComObject WScript.Network).SetDefaultPrinter($PrinterName)
                Write-Host "✅ Impresora establecida como predeterminada" -ForegroundColor Green
            } catch {
                Write-Host "⚠️  No se pudo establecer como predeterminada" -ForegroundColor Yellow
            }
        }
    }
}

function Test-PrinterInstallation {
    Write-Host "🔍 Verificando instalación..." -ForegroundColor Blue
    
    $printer = Get-Printer -Name $PrinterName -ErrorAction SilentlyContinue
    
    if ($printer) {
        Write-Host "✅ Impresora instalada correctamente" -ForegroundColor Green
        Write-Host ""
        Write-Host "Estado: $($printer.PrinterStatus)" -ForegroundColor White
        Write-Host "Puerto: $($printer.PortName)" -ForegroundColor White
        Write-Host "Driver: $($printer.DriverName)" -ForegroundColor White
        return $true
    } else {
        Write-Host "❌ La impresora no se encuentra instalada" -ForegroundColor Red
        return $false
    }
}

function Print-TestPage {
    $response = Read-Host "`n¿Deseas imprimir una página de prueba? (S/N)"
    
    if ($response -match '^[Ss]$') {
        try {
            Write-Host "🖨️  Imprimiendo página de prueba..." -ForegroundColor Blue
            
            # Crear archivo temporal con página de prueba
            $testContent = @"
╔════════════════════════════════╗
║  ONE-POS Network Printer       ║
║  Página de Prueba              ║
╠════════════════════════════════╣
║                                ║
║  ✓ Instalación exitosa         ║
║  ✓ Conexión establecida        ║
║  ✓ Lista para imprimir         ║
║                                ║
║  Fecha: $(Get-Date -Format 'yyyy-MM-dd HH:mm')
║                                ║
╚════════════════════════════════╝
"@
            
            $tempFile = [System.IO.Path]::GetTempFileName()
            $testContent | Out-File -FilePath $tempFile -Encoding UTF8
            
            # Imprimir
            Start-Process -FilePath "notepad.exe" -ArgumentList "/p $tempFile" -Wait
            
            Write-Host "✅ Página de prueba enviada" -ForegroundColor Green
            
            # Limpiar archivo temporal
            Start-Sleep -Seconds 2
            Remove-Item -Path $tempFile -Force -ErrorAction SilentlyContinue
        } catch {
            Write-Host "⚠️  No se pudo imprimir la página de prueba: $_" -ForegroundColor Yellow
        }
    }
}

function Show-SuccessInfo {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "        ✅ INSTALACIÓN COMPLETADA EXITOSAMENTE" -ForegroundColor Green
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "📋 Información de la impresora:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Nombre: $PrinterName" -ForegroundColor White
    Write-Host "  URL: $PrinterURL" -ForegroundColor White
    Write-Host ""
    Write-Host "🔧 La impresora está lista para usar desde cualquier aplicación." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Para ver propiedades:" -ForegroundColor Cyan
    Write-Host "  Panel de Control > Dispositivos e Impresoras" -ForegroundColor White
    Write-Host ""
}

function Show-ManualInstructions {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  ⚠️  INSTALACIÓN AUTOMÁTICA FALLIDA" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Por favor, instala manualmente siguiendo estos pasos:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. Abrir: Panel de Control > Dispositivos e Impresoras" -ForegroundColor White
    Write-Host "2. Clic en: 'Agregar una impresora'" -ForegroundColor White
    Write-Host "3. Seleccionar: 'La impresora que deseo no está en la lista'" -ForegroundColor White
    Write-Host "4. Seleccionar: 'Agregar impresora mediante dirección TCP/IP'" -ForegroundColor White
    Write-Host "5. Ingresar URL: $PrinterURL" -ForegroundColor Cyan
    Write-Host ""
}

# ############################################################################
# Script principal
# ############################################################################

function Main {
    Write-Banner
    
    Write-Host "📦 Parámetros de instalación:" -ForegroundColor Blue
    Write-Host "  Servidor: $ServerIP"
    Write-Host "  Puerto: $ServerPort"
    Write-Host ""
    
    # Verificar permisos de administrador
    if (-not (Test-Administrator)) {
        Write-Host "❌ Este script debe ejecutarse como Administrador" -ForegroundColor Red
        Write-Host ""
        Write-Host "Haz clic derecho en el archivo y selecciona:" -ForegroundColor Yellow
        Write-Host "'Ejecutar como administrador'" -ForegroundColor Yellow
        Write-Host ""
        Read-Host "Presiona Enter para salir"
        exit 1
    }
    
    Write-Host "✅ Permisos de administrador verificados" -ForegroundColor Green
    Write-Host ""
    
    # Proceso de instalación
    Remove-ExistingPrinter
    
    $portCreated = Add-IPPPort
    
    if ($portCreated) {
        $installed = Install-Printer
        
        if ($installed) {
            $verified = Test-PrinterInstallation
            
            if ($verified) {
                Set-DefaultPrinter
                Print-TestPage
                Show-SuccessInfo
            } else {
                Show-ManualInstructions
            }
        } else {
            Show-ManualInstructions
        }
    } else {
        Write-Host "⚠️  Intentando instalación alternativa..." -ForegroundColor Yellow
        Show-ManualInstructions
    }
    
    Write-Host ""
    Read-Host "Presiona Enter para salir"
}

# Ejecutar script principal
Main
