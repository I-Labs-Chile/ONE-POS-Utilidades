# ONE-POS-Utilities — Herramienta para impresoras térmicas

Este proyecto está diseñado para:
- **Testear impresoras térmicas** a nivel bajo, incluyendo detección de dispositivos y envío de comandos ESC/POS.
- **Desarrollar un servidor de impresión** que permita gestionar impresoras térmicas conectadas por USB o puerto serial.

## Tecnologías y características
- **Dispositivos soportados**: Impresoras térmicas que usan puertos seriales (`/dev/tty*`) o el módulo `usblp` (`/dev/usb/lp*`).
- **Comandos ESC/POS**: Envío de datos RAW para formateo de tickets, cortes de papel, códigos de barras, etc.
- **Python**: Scripts para detección, pruebas y manejo de impresoras.
- **PySerial y Python-ESC/POS**: Librerías para comunicación con dispositivos seriales y formateo avanzado.

## Archivos principales
- `detect_printer.py`: Lista puertos seriales y detecta impresoras USB gestionadas por `usblp`.
- `printer_commands.py`: Utilidades y comandos ESC/POS (inicialización, corte, formateo de tickets).
- `print_raw.py`: Ejemplo de envío de datos RAW a una impresora serial.
- `print_escpos.py`: Ejemplo de uso de la librería `python-escpos`.
- `print_usb_lp.py`: Ejemplo de impresión directa en `/dev/usb/lp0`.
- `requirements.txt`: Dependencias necesarias.
- `tests/`: Tests unitarios que no requieren hardware.

## Instrucciones rápidas

1. **Instalar dependencias** (recomendado en un entorno virtual):

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **Detectar el puerto de la impresora**:

```bash
python detect_printer.py
```

Busca el `device` correspondiente (ej. `/dev/ttyUSB0` o `/dev/usb/lp0`).

3. **Probar impresión RAW**:

```bash
python print_raw.py
```

4. **Probar con `python-escpos`**:

```bash
python print_escpos.py
```

5. **Impresoras USB gestionadas por `usblp`**:

Algunas impresoras térmicas USB (p. ej. Xprinter) son detectadas por el kernel como "USB Printer" y usan el módulo `usblp`. En ese caso, basta con abrir el archivo del dispositivo y escribir datos RAW ESC/POS:

```python
with open('/dev/usb/lp0', 'wb') as f:
    f.write(b"Hola\n")
```

Ejemplo con el script `print_usb_lp.py`:

```bash
python print_usb_lp.py /dev/usb/lp0
```

## Permisos y debugging

- **Permisos**: Agrega tu usuario al grupo `lp` o `dialout` para acceder a los dispositivos:

```bash
sudo usermod -a -G lp $USER
# Cierra sesión y vuelve a entrar
```

- **Debugging**: Revisa `dmesg | tail` al conectar el cable y prueba distintos baudios (9600, 19200, 38400).

## Tests unitarios

Ejecuta los tests unitarios (no requieren impresora):

```bash
pytest -q
```
