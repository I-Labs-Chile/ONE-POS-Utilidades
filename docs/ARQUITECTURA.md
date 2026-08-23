# Arquitectura del proyecto

Dos utilidades FastAPI independientes que imprimen en impresoras térmicas ESC/POS. Todo el procesamiento es local: no usa CUPS ni IPP.

```
┌─ Servidor web (app/, run.py, :8080) ────────┐   ┌─ Cabina (cabina/, run_cabina.py, :8081) ─┐
│ Navegador ──HTTP──▶ api.py                  │   │ Kiosco ──getUserMedia──▶ webcam           │
│   /imprimir /imprimir-imagen /cola /salud   │   │   │ POST /captura (3 fotos)               │
│                                             │   │   ▼                                       │
│         PDF ──pdftoppm──▶ PNGs              │   │ compose.py: tira 384px                    │
│         Imagen ──▶ PIL                      │   │ (crop 4:3 + apilado + logo + QR)          │
│                    │                        │   │                                           │
└────────────────────┼────────────────────────┘   └───────────────────┬───────────────────────┘
                     │              onepos_common/ (librería interna)  │
                     └──────────────────────┬──────────────────────────┘
                                            ▼
        PrintQueue (queue.py) ── persistencia ./data[/data-cabina]/queue.json
                                            │
        PrintWorker (worker.py, hilo daemon, secuencial)
                                            │
                    to_thermal_mono_dither (image.py)
                                            ▼
                    create_sender (printer_manager.py)
                        ├─ Windows → WindowsEscposSender (spooler RAW)
                        └─ Linux   → EscposSender (TCP / USB)
```

**Regla estructural:** `onepos_common/` es la librería interna compartida y **nunca** importa de `app/` o `cabina/`. Las dependencias van en un solo sentido: apps → common. El worker recibe el selftest de bienvenida inyectado (`PrintWorker(queue, selftest_fn=...)`) porque el ticket de bienvenida es cosa del servidor, no de la cabina.

## Módulos

### `onepos_common/` — stack térmico compartido

| Módulo | Rol |
|---|---|
| `queue.py` | Cola FIFO persistente |
| `worker.py` | Hilo de procesamiento secuencial |
| `status.py` | Monitor de impresora (`PrinterMonitor`, snapshot thread-safe cada 3 s) |
| `image.py` | Pipeline térmico de imagen |
| `escpos.py` | Sender Linux (TCP/USB) |
| `printer_manager.py` + `windows_spooler.py` | Selección de backend y spooler RAW Windows |
| `network.py`, `usb_detector.py`, `usb_printer.py` | IP local y detección USB |

### `app/web/api.py` (servidor)
Endpoints HTTP:

| Endpoint | Método | Descripción |
|---|---|---|
| `/` | GET | Interfaz web (drag & drop) |
| `/imprimir` | POST | Sube PDF y encola |
| `/imprimir-imagen` | POST | Sube imagen y encola |
| `/cola` | GET | Estado de la cola |
| `/salud` | GET | Healthcheck (usado por el frontend cada 3 s) |
| `/estado` | GET | IP local y configuración |

Además lanza en `startup` el worker (con selftest inyectado) y el monitor de impresora de `onepos_common.status`.

### `onepos_common/queue.py`
Cola FIFO persistente en JSON (escritura atómica vía archivo temporal + `os.replace`). Estados: `pendiente → procesando → impreso | error`. Mantiene cache de los últimos 10 trabajos impresos y de los últimos 10 errores (visibles en `/cola` bajo la clave `errores`).

> Nota conocida: si el proceso muere mientras un trabajo está `procesando`, ese trabajo se pierde (se retiró de la cola antes de imprimir). No se re-encola automáticamente; una mejora posible sería moverlo a un estado "en proceso" persistido al momento del dequeue.

### `onepos_common/worker.py`
Hilo daemon que procesa la cola estrictamente en secuencia:
1. PDF → `pdftoppm -png -r $RASTER_DPI` (requiere poppler; las páginas se recolectan con glob para soportar el zero-padding de 10+ páginas)
2. Cada página/imagen pasa por `to_thermal_mono_dither`
3. Envío por el sender y corte de papel

Al arrancar ejecuta `selftest_fn` si fue inyectada (el servidor pasa `test_print.py`, que imprime un ticket de bienvenida con QR).

### `cabina/` — kiosco fotográfico

- `api.py`: endpoints propios — `/` (kiosco), `/salud` (mismo contrato que el servidor, vía `status.py`), `POST /captura` (multipart `foto1,foto2,foto3`). Valida disponibilidad de impresora, compone la tira **en color**, guarda el PNG en el jobs dir y encola `PrintJob(kind="image")`; el dithering mono ocurre una sola vez en el worker común.
- `compose.py`: `_load_rgb` (EXIF transpose) → crop central 4:3 → resize al ancho del papel → apilado vertical con márgenes → fila final con logo (~55% ancho) + QR (~33% ancho).
- `frontend/`: kiosco HTML/CSS/JS estático. Máquina de estados PREVIEW → COUNTDOWN(3·2·1 ×3 fotos) → REVIEW → PRINTING. Webcam 100% cliente vía `getUserMedia`; consulta `/salud` cada 3 s y encuesta `/cola` para feedback de impresión.
- Datos separados por diseño: `run_cabina.py` fija defaults `SERVER_PORT=8081` y `QUEUE_DIR=./data-cabina` antes de importar módulos.

### `onepos_common/image.py`
Pipeline térmico: resize al ancho del papel → grises → normalización de brillo (corrige <100 / >180) → auto-niveles con percentiles 2–98 → dithering Floyd–Steinberg → 1-bit.

> Rendimiento conocido: Floyd–Steinberg está implementado con bucles Python puros; en páginas grandes (PDF carta/A4 a 203 dpi ≈ 3,5 M píxeles) tarda varios segundos por página. Una vectorización fila-a-fila con NumPy sería la mejora natural.

### `onepos_common/escpos.py`
`EscposSender` para Linux: TCP raw socket o USB con tres backends en cascada — `USBPrinterBackend` (detección de `/dev/usb/lp*`), PyUSB/libusb (bulk OUT), y escritura directa al nodo de dispositivo. Comandos: init, text (cp437), QR (modelo 2), raster `GS v 0`, cut, feed.

### `onepos_common/windows_spooler.py` + `printer_manager.py`
En Windows no existen nodos `/dev/...`: se envía ESC/POS como trabajo **RAW** al Print Spooler (`win32print.StartDocPrinter(..., "RAW")`). El driver puede filtrar el corte, por eso `cut()` es best-effort.

`create_sender()` elige backend por SO (o forzado con `PRINTER_BACKEND=windows|linux`, útil en desarrollo). El nombre de impresora se resuelve con `resolve_printer_name()`:

1. `PRINTER_NAME` / `WINDOWS_PRINTER_NAME` del entorno (coincidencia exacta o por prefijo)
2. Patrones térmicos conocidos: `POS-58`, `POS-80`, `pos`, `thermal`, `receipt`
3. Primera impresora instalada

Esto existe porque reinstalar el driver genera nombres versionados ("POS-58 (Copia 1)") y un hardcodeo rompía la detección.

### `onepos_common/network.py` / `usb_detector.py` / `usb_printer.py`
IP primaria (UDP trick hacia 8.8.8.8) y detección de impresoras USB en Linux (nodos de dispositivo, `lsusb -v`, sysfs).

> Limitación conocida: `_enrich_with_usb_info` asigna metadatos del primer dispositivo USB que tenga campos faltantes sin correlacionar bus/device, por lo que con múltiples dispositivos USB los fabricantes/productos pueden mezclarse entre impresoras. No afecta la ruta de escritura (usa device_path).

### Frontends
- `app/web/frontend/`: drag & drop, click y paste; consulta `/salud` cada 3 s y bloquea la zona de carga si la impresora no está disponible.
- `cabina/frontend/`: ver sección cabina.

## Variables de entorno

Ver `.env.example` en la raíz (servidor) y `cabina/.env.example` (cabina). Se cargan con `python-dotenv` desde sus entrypoints (también funcionan exportadas en el shell).

## Empaquetado

PyInstaller onefile con specs versionados en `build/*.spec` (4 specs: servidor y cabina × Linux y Windows). Ver [BUILD.md](BUILD.md). Los releases se generan automáticamente por GitHub Actions al crear tags `v*`.
