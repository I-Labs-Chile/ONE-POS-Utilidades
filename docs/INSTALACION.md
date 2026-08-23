# Guía de instalación

Servidor de impresión ESC/POS para impresoras térmicas (Q-Cube y compatibles). Permite imprimir PDF e imágenes desde cualquier navegador de la red local.

## Descarga

Descarga la última versión desde [GitHub Releases](https://github.com/I-Labs-Chile/ONE-POS-Utilidades/releases):

- Windows: `escpos-server-windows-x64-vX.Y.Z.zip`
- Linux: `escpos-server-linux-x64-vX.Y.Z.tar.gz`

---

## Windows

### 1. Instalar el driver de la impresora

Instala el driver POS una sola vez con la impresora conectada y encendida:
[POS Printer Driver Setup V8.203.exe](https://github.com/CrisAlva1414/ONE-POS-Driver/raw/refs/heads/main/Driver/Windows%20Driver/POS%20Printer%20Driver%20Setup%20V8.203.exe)

> Si el driver se instaló más de una vez, Windows crea nombres como `POS-58 (Copia 1)`. El servidor autodetecta la impresora correcta; si tu caso es especial, define `PRINTER_NAME` en `.env` con el nombre exacto que aparece en *Panel de control → Dispositivos e impresoras*.

### 2. Extraer y ejecutar

1. Extrae el ZIP descargado
2. Ejecuta `escpos-server.exe` (si Windows lo bloquea: clic derecho → **Propiedades** → **Desbloquear**, o "Ejecutar como administrador")
3. Abre `http://localhost:8080`

### Notas

- Para imprimir **PDF** se necesita `pdftoppm.exe` (Poppler para Windows) junto al ejecutable o en el `PATH`. Sin él solo se pueden imprimir imágenes.
- Si no accedes desde otra máquina, permite el puerto 8080 en el firewall.
- También puedes lanzar con `launch-server-windows.ps1` para ver los logs en una consola dedicada.

---

## Linux (Debian/Ubuntu)

### 1. Dependencias del sistema (una sola vez)

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils libusb-1.0-0
sudo usermod -a -G lp $USER   # permisos USB; cerrar sesión y volver a entrar
```

### 2. Extraer y ejecutar

```bash
tar -xzf escpos-server-linux-x64-v*.tar.gz
cd escpos-server-linux-x64-v*/
./launch-server.sh        # o doble click en escpos-server.desktop
```

Abre `http://localhost:8080`.

---

## Usar la interfaz

1. Desde el mismo computador: `http://localhost:8080`
2. Desde celular u otro PC en la misma red: `http://IP-DEL-SERVIDOR:8080`
   - La IP aparece al iniciar el servidor, o se consulta en `/estado`
3. Arrastra un archivo (o haz click / pega) para imprimirlo

**Formatos soportados:** PDF, JPG, PNG, BMP, GIF, WEBP.

Al iniciar, el servidor imprime automáticamente un ticket de bienvenida con un QR hacia la interfaz web.

## Configuración opcional

```bash
cp .env.example .env
nano .env    # editar y reiniciar el servidor
```

| Variable | Descripción | Por defecto |
|---|---|---|
| `PRINTER_IF` | `usb` o `tcp` | `usb` |
| `PRINTER_HOST` / `PRINTER_PORT` | Impresora de red | `127.0.0.1:9100` |
| `USB_VENDOR` / `USB_PRODUCT` | IDs USB específicos (autodetección si se omiten) | vacío |
| `PRINTER_NAME` | Nombre de impresora en Windows (si la autodetección falla) | autodetectada |
| `PAPER_WIDTH_PX` | 384 = 58mm, 576 = 80mm | `384` |
| `RASTER_DPI` | DPI al rasterizar PDF | `203` |
| `SERVER_PORT` | Puerto HTTP | `8080` |
| `QUEUE_DIR` | Directorio de datos | `./data` |

## Solución de problemas

| Síntoma | Solución |
|---|---|
| "No se encuentra la impresora" (Linux) | Verifica `lsusb`; revisa permisos con `ls -l /dev/usb/lp*`; agrega tu usuario al grupo `lp` |
| "Permission denied" en `/dev/usb/lp0` | `sudo usermod -a -G lp $USER` y reinicia sesión |
| Puerto 8080 ocupado | Cambia `SERVER_PORT` en `.env`, o libera el puerto: `sudo lsof -ti:8080 \| xargs kill` |
| No accedo desde otro dispositivo | Misma red; abre el puerto en el firewall (`sudo ufw allow 8080`) |
| Impresión muy oscura/clara | El servidor normaliza automáticamente; verifica calidad del papel térmico y densidad del cabezal |
| PDF no imprime en Windows | Falta `pdftoppm.exe` (Poppler); colócalo junto al ejecutable |
| Impresión cortada o mal ancho | Ajusta `PAPER_WIDTH_PX` (384 para 58mm, 576 para 80mm) |

## Soporte

- Issues: <https://github.com/I-Labs-Chile/ONE-POS-Utilidades/issues>
- Email: soporte@i-labs.cl
