# ONE-POS Utilidades · Servidor de impresión ESC/POS ligero

Un servicio de impresión minimalista y robusto para retail, pensado para correr en Raspberry Pi Zero y PCs Linux. No usa CUPS/IPP ni drivers del sistema: envía bytes ESC/POS directamente por USB o TCP.

- Soporta PDF → raster → monocromo con dithering → ESC/POS
- Impresión secuencial con cola persistente
- API HTTP simple para subir y monitorear trabajos
- Diseñado para bajo consumo de recursos y empaquetable como binario único

## Características
- FastAPI como servidor HTTP
- Poppler (`pdftoppm`) para rasterizar PDF
- Pillow para procesamiento de imagen (grises, 1bpp)
- USB: PyUSB/libusb o archivo de dispositivo `/dev/usb/lp*`
- TCP: raw socket (ej. impresoras de red en 9100)
- Cola persistente en JSON con últimos 10 impresos en cache
- Logs y comentarios en español, orientados a diagnóstico en campo

## Requisitos
- Python 3.9+ (probado en 3.11)
- Sistema: `poppler-utils` y `libusb-1.0`
- Permisos de acceso a USB (grupo `lp` o reglas `udev`)

## Instalación rápida
```bash
sudo apt-get update && sudo apt-get install -y poppler-utils libusb-1.0-0
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecución
```bash
uvicorn app.web.api:app --host 0.0.0.0 --port 8080
# o
python run.py
```

## Endpoints
- POST `/imprimir`: subir PDF y encolar impresión
- GET `/cola`: estado de cola (pendientes e impresos)
- GET `/salud`: healthcheck con métricas básicas
- GET `/estado`: IP local del dispositivo y configuración de impresora

## Variables de entorno principales
- `PRINTER_IF`: `tcp` o `usb`
- `PRINTER_HOST`: IP/host de impresora TCP
- `PRINTER_PORT`: puerto TCP (por defecto 9100)
- `USB_VENDOR`, `USB_PRODUCT`: IDs para PyUSB (hex o int). Si no se definen, se intenta autodetección por archivo de dispositivo.
- `PAPER_WIDTH_PX`: ancho en píxeles (ej. 384 para 58mm, 576 para 80mm)
- `QUEUE_DIR`: ruta para datos y cola (por defecto `./data`)

## Flujo de impresión
1. El cliente sube un PDF vía `/imprimir`
2. Se encola el trabajo con metadatos (id, IP cliente, nombre, fecha)
3. Worker secuencial:
   - Rasteriza PDF con `pdftoppm` (PNG por página)
   - Convierte a 1bpp con dithering
   - Genera comandos ESC/POS y envía por TCP/USB
   - Actualiza estado del trabajo (procesando/impreso/error)

## Cola y persistencia
- Mantiene todos los trabajos no impresos
- Cachea los últimos 10 impresos
- Limpia automáticamente los impresos que superen el límite
- Estado en `./data/queue.json` y archivos temporales en `./data/jobs/`

## Servicio systemd
1. Ajusta `deploy/escpos-server.service` a tu ruta real y usuario
2. Copia y habilita:
```bash
sudo cp deploy/escpos-server.service /etc/systemd/system/escpos-server.service
sudo systemctl daemon-reload
sudo systemctl enable escpos-server
sudo systemctl start escpos-server
```

## Empaquetar como binario único
```bash
pip install pyinstaller
pyinstaller --onefile --name escpos-server run.py
```

## Diagnóstico rápido
- Verifica IP local: `GET /estado`
- USB sin PyUSB: asegúrate que exista `/dev/usb/lp0` o similar y permisos de escritura
- PyUSB: instala `pyusb` y `libusb-1.0`, exporta `USB_VENDOR` y `USB_PRODUCT` si necesitas forzar el dispositivo
- Rasterización: confirma `pdftoppm -v`
- Ancho de papel: ajusta `PAPER_WIDTH_PX` al modelo de tu impresora

## Estructura del proyecto
- `run.py`: punto de entrada
- `app/web/api.py`: API FastAPI
- `app/core/queue.py`: cola persistente
- `app/core/worker.py`: worker de impresión
- `app/utils/escpos.py`: envío ESC/POS por TCP/USB
- `app/utils/image.py`: conversión y dithering
- `app/utils/network.py`: IP local del dispositivo

## Notas
- No se usa CUPS, IPP ni drivers del sistema
- Impresión estrictamente secuencial, sin concurrencia en el envío
- Diseñado para estabilidad en hardware de bajos recursos

