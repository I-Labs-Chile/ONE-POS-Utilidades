# 🖨️📸 ONE-POS Utilidades — Impresión térmica ESC/POS

Dos utilidades independientes para impresoras térmicas ESC/POS (Q-Cube y compatibles), desarrolladas por I-Labs Chile. Sin CUPS, sin IPP: comandos ESC/POS directos por USB o TCP.

| Utilidad | Binario | Qué hace |
|---|---|---|
| **Servidor de impresión** | `escpos-server` | Imprime PDF e imágenes desde cualquier navegador de la red local (drag & drop) |
| **Cabina fotográfica** | `escpos-cabina` | Kiosco de fotos con webcam: 3 fotos + logo + QR en una tira impresa |

- **Windows**: impresión vía Print Spooler RAW (autodetección de la impresora)
- **Linux**: USB (`/dev/usb/lp*` / PyUSB) o TCP raw
- PDF rasterizado con Poppler + dithering Floyd–Steinberg para calidad térmica

## Inicio rápido

### Servidor de impresión

**Linux**

```bash
sudo apt-get install -y poppler-utils libusb-1.0-0
sudo usermod -a -G lp $USER    # cerrar sesión y volver a entrar
tar -xzf escpos-server-linux-x64-v*.tar.gz && cd escpos-server-linux-x64-v*/
./launch-server.sh             # o doble click en escpos-server.desktop
```

**Windows**

1. Instala el [driver POS](https://github.com/CrisAlva1414/ONE-POS-Driver/raw/refs/heads/main/Driver/Windows%20Driver/POS%20Printer%20Driver%20Setup%20V8.203.exe)
2. Extrae el ZIP y ejecuta `escpos-server.exe`
3. Abre `http://localhost:8080`

> Para imprimir PDF en Windows se necesita `pdftoppm.exe` (Poppler) junto al ejecutable; los releases generados por CI ya lo incluyen.

Arrastra un archivo en la web y se imprime. Al arrancar, el servidor imprime un ticket con QR hacia la interfaz.

### Cabina fotográfica

Mismo esquema de paquetes (`escpos-cabina-*`): ejecuta el binario, abre `http://localhost:8081`, permite la cámara y presiona FOTO. Guía completa en [docs/CABINA.md](docs/CABINA.md).

## Desarrollo

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py                  # servidor web: http://localhost:8080
python run_cabina.py           # cabina:        http://localhost:8081
```

La configuración se toma del entorno y de `.env` (ver [.env.example](.env.example)).

## API

### Servidor (`escpos-server`)

| Endpoint | Método | Descripción |
|---|---|---|
| `/` | GET | Interfaz web |
| `/imprimir` | POST | Encola un PDF |
| `/imprimir-imagen` | POST | Encola una imagen |
| `/cola` | GET | Estado de la cola |
| `/salud` | GET | Healthcheck con estado de impresora |
| `/estado` | GET | IP local y configuración |
| `/test-impresora` | POST | Imprime ticket de prueba |

### Cabina (`escpos-cabina`)

| Endpoint | Método | Descripción |
|---|---|---|
| `/` | GET | Interfaz kiosco |
| `/captura` | POST | Recibe 3 fotos, compone la tira y encola |
| `/salud` | GET | Healthcheck con estado de impresora |

## Documentación

- [Instalación y uso](docs/INSTALACION.md)
- [Cabina fotográfica](docs/CABINA.md)
- [Arquitectura y código](docs/ARQUITECTURA.md)
- [Build y releases](docs/BUILD.md)

## Soporte

Issues: <https://github.com/I-Labs-Chile/ONE-POS-Utilidades/issues> · soporte@i-labs.cl

---

**Desarrollado por I-Labs Chile** · Licencia MIT (ver [LICENSE](LICENSE))
