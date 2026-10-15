# AGENTS.md — ONE-POS-Utilidades

Guía operativa para agentes que trabajen en este repo. Leer antes de tocar código.

## Qué es

Servidor de impresión ESC/POS para impresoras térmicas (Q-Cube y compatibles) pensado para retail. Imprime PDF e imágenes desde el navegador. Contiene **dos utilidades independientes** sobre un núcleo compartido:

- **Servidor** (`run.py`, `app/`) — sube PDF/imagen vía web y las imprime. Puerto HTTP `8080`.
- **Cabina fotográfica** (`run_cabina.py`, `cabina/`) — tira de fotos. Puerto HTTP `8081`.
- **Núcleo compartido** (`onepos_common/`) — cola, worker, ESC/POS, imagen, detección de impresora y backends por SO.

## Stack

- Python 3.9+ (CI usa 3.12), FastAPI + Uvicorn.
- Pillow + NumPy para rasterizado y dithering; `qrcode` para QR.
- `pyusb` (Linux, USB crudo) y `pywin32` (Windows, `win32print` → spooler RAW).
- Poppler (`pdftoppm`) para rasterizar PDFs (no se empaqueta en el binario; ver docs/BUILD.md).
- PyInstaller para los 4 binarios; specs versionados en `build/`.

## Impresión por sistema operativo (crítico)

- **Linux**: `onepos_common/escpos.py` — pyusb/libsub con fallback a `/dev/usb/lp*`.
- **Windows**: `onepos_common/windows_spooler.py` — envía ESC/POS **RAW** al spooler vía `win32print` (`StartDocPrinter`/`WritePrinter`/`EndDocPrinter`). Requiere `pywin32`.
- El selector es `onepos_common/printer_manager.create_sender()`; se puede forzar con `PRINTER_BACKEND=windows|linux` (solo desarrollo).
- `requirements.txt` **debe** incluir `pywin32; sys_platform == "win32"`. Si falta, el build de Windows compila igual pero el ejecutable falla al imprimir con `No module named 'win32print'`. No borrar esa línea.

## Estructura

```
run.py / run_cabina.py     # puntos de entrada
app/                       # utilidad servidor (FastAPI)
cabina/                    # utilidad cabina fotográfica
onepos_common/             # núcleo compartido (queue, worker, escpos, image, printer_manager, status, windows_spooler, usb_*)
build/                     # specs PyInstaller, scripts de build, lanzadores, .desktop
docs/                      # INSTALACION, BUILD, ARQUITECTURA, CABINA + sessions/, adr/, format/
.github/workflows/release.yml  # release al crear tag v*
```

## Comandos

```bash
# Entorno
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Ejecutar en desarrollo
python run.py            # servidor  → http://localhost:8080
python run_cabina.py     # cabina    → http://localhost:8081

# Build local
./build/build_linux.sh  [servidor|cabina|ambos]     # Linux/macOS
build\build_windows.bat [servidor|cabina|ambos]     # Windows (cmd)

# Release: bump version en pyproject.toml, commit, tag vX.Y.Z y push.
# El tag DEBE coincidir con la version de pyproject.toml (lo valida el CI).
```

No hay suite de tests automatizada. La verificación es smoke manual: levantar el servidor y probar `/`, `/salud`, `/estado`, `/test-impresora`.

## Convenciones

- **Commits**: Conventional Commits, en inglés, imperativo (`fix(windows): ...`).
- **Rama de integración**: `main` (no existe `develop`). `pull` antes de trabajar y antes de `push`.
- **Logs**: el proyecto usa `print()` con prefijo `#` (orientado a diagnóstico de campo). Mantener ese estilo.
- **Idioma**: comentarios, mensajes y docs en español neutro.
- **Dependencias**: cualquier dependencia Python nueva va en `requirements.txt` **y** en `pyproject.toml`.

## Documentación

- `docs/INSTALACION.md` — instalación usuario final (Windows/Linux).
- `docs/BUILD.md` — builds y release.
- `docs/ARQUITECTURA.md` — diseño del núcleo compartido.
- `docs/CABINA.md` — utilidad cabina.
- `docs/sessions/` — bitácora de sesiones.
- `docs/adr/` — decisiones de arquitectura.
- `docs/format/` — convenciones de formato/estilo.
