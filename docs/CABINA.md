# 📸 Cabina Fotográfica ONE-POS

Kiosco de fotos para impresora térmica: toma **3 fotos seguidas** con la webcam, las compone en una tira vertical con el logo de I-Labs y un QR, y la imprime. Utilidad **totalmente independiente** del servidor de impresión web: binario propio (`escpos-cabina`), puerto y datos propios.

```
Navegador (kiosco) ──getUserMedia──▶ webcam
        │
        │ POST /captura (3 fotos JPEG)
        ▼
FastAPI cabina ──compose_strip()──▶ tira PNG 384px
        │                              (3 fotos + logo + QR)
        ▼
onepos_common (cola + worker + dithering + sender ESC/POS) ──▶ impresora térmica
```

## Requisitos

- Impresora térmica instalada:
  - **Linux**: `libusb-1.0-0`, usuario en grupo `lp`
  - **Windows**: driver POS instalado (autodetección POS-58/POS-80/Thermal)
- Webcam USB integrada o externa
- Navegador Chromium/Chrome/Edge (por `getUserMedia`)

## Uso

### Linux

```bash
tar -xzf escpos-cabina-linux-x64-v*.tar.gz && cd escpos-cabina-linux-x64-v*/
./launch-cabina.sh              # o doble click en escpos-cabina.desktop
```

Abre `http://localhost:8081`, permite la cámara y presiona FOTO.

### Windows

1. Instala el [driver POS](https://github.com/CrisAlva1414/ONE-POS-Driver/raw/refs/heads/main/Driver/Windows%20Driver/POS%20Printer%20Driver%20Setup%20V8.203.exe)
2. Extrae el ZIP y ejecuta `escpos-cabina.exe`
3. Abre `http://localhost:8081` y permite la cámara

### Controles

| Acción | Tecla | Botón |
|---|---|---|
| Iniciar sesión de fotos | `Espacio` / `F` | 📸 FOTO |
| Imprimir la tira | `Enter` / `A` | 🖨️ IMPRIMIR |
| Repetir / cancelar | `Esc` / `R` | ↺ REPETIR |

Flujo: cuenta regresiva 3·2·1 → tres capturas con flash → revisión de miniaturas → impresión.

## Configuración

Copia `.env.example` a `.env` junto al ejecutable:

| Variable | Default | Descripción |
|---|---|---|
| `SERVER_PORT` | `8081` | Puerto del kiosco |
| `QUEUE_DIR` | `./data-cabina` | Datos propios (no comparte con el servidor) |
| `PAPER_WIDTH_PX` | `384` | Ancho papel: `384` = 58 mm, `576` = 80 mm |
| `CABINA_QR_URL` | `https://www.instagram.com/ilabs.cl/` | Destino del QR impreso |
| `PRINTER_IF` | `usb` | Interfaz: `usb` \| `tcp` |
| `THERMAL_GAMMA` | `1.4` | Gamma del pipeline foto: >1 aclara sombras (sube a 1.6 si ves barba/pelo tapado; baja a 1.2 si el resultado sale lavado) |
| `THERMAL_BRIGHTNESS_TARGET` | `128` | Media de brillo objetivo antes de la gamma |

## Convivencia con el servidor web

Ambas utilidades pueden correr a la vez (puertos 8081 y 8080, datos separados). La cola de la cabina es exclusiva: los trabajos no se mezclan con los del servidor.

## Desarrollo

```bash
source .venv/bin/activate
python run_cabina.py            # http://localhost:8081
```

- `cabina/api.py`: endpoints `/` (kiosco), `/salud` y `/captura`
- `cabina/compose.py`: composición de la tira (crop 4:3, apilado, logo + QR)
- `cabina/frontend/`: kiosco HTML/CSS/JS estático
- El stack térmico es compartido vía [`onepos_common/`](ARQUITECTURA.md): misma cola, dithering y senders que el servidor
