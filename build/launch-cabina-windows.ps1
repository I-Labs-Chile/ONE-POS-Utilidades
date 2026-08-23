<#
Lanza el ejecutable `escpos-cabina.exe` en primer plano para que
sus logs se muestren en la terminal. Si la ventana se cierra,
el proceso también se cerrará (al estar adjunto a la misma consola).

Colócalo junto al release o en la carpeta del ejecutable dentro
del paquete de build.
#>

Param(
    [string]$ExePath
)

function Find-Exe {
    param($base)
    $found = Get-ChildItem -Path $base -Filter escpos-cabina.exe -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
    return $found
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($ExePath) {
    $exe = Get-Item -LiteralPath $ExePath -ErrorAction SilentlyContinue
} else {
    $exe = Find-Exe -base $scriptDir
    if (-not $exe) {
        $parent = (Get-Item $scriptDir).Parent
        if ($parent) { $exe = Find-Exe -base $parent.FullName }
    }
}

if (-not $exe) {
    Write-Error "No se encontró 'escpos-cabina.exe'. Coloca este script en la carpeta del release o especifica -ExePath.";
    exit 2
}

$exeDir = $exe.DirectoryName
Push-Location $exeDir

Write-Host "===============================================" -ForegroundColor Magenta
Write-Host " Cabina Fotográfica ONE-POS - Escpos Cabina" -ForegroundColor Magenta
Write-Host " Logs en tiempo real (Ctrl+C para detener)" -ForegroundColor Magenta
Write-Host "===============================================`n" -ForegroundColor Magenta

try {
    Write-Host "Iniciando: $($exe.FullName)`n"
    & "$($exe.FullName)"
    $exitCode = $LASTEXITCODE
} catch {
    Write-Error "Error al ejecutar la cabina: $_"
    $exitCode = 1
} finally {
    Write-Host "`n===============================================" -ForegroundColor Magenta
    Write-Host "La cabina se ha detenido. Código de salida: $exitCode" -ForegroundColor Yellow
    Write-Host "Presiona Enter para cerrar esta ventana..."
    [void][System.Console]::ReadLine()
    Pop-Location
}

exit $exitCode
