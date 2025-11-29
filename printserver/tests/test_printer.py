#!/usr/bin/env python3

from hardware.usb_detector import USBPrinterDetector
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Herramienta diagnóstica principal para detectar e inspeccionar impresoras USB
def main():
    print("=" * 70)
    print("HERRAMIENTA DE DIAGNÓSTICO DE IMPRESORA USB")
    print("=" * 70)
    print()
    detector = USBPrinterDetector()
    print("🔍 Buscando impresoras USB...")
    print()
    printers = detector.scan_for_printers()

    if not printers:
        print("❌ No se encontraron impresoras!")
        print()
        print("Resolución de problemas:")
        print("  1. Verificar conexión USB")
        print("  2. Confirmar que la impresora esté encendida")
        print("  3. Revisar permisos: ls -l /dev/usb/lp*")
        print("  4. Agregar usuario al grupo lp: sudo usermod -a -G lp $USER")
        print("  5. Instalar usbutils: sudo apt install usbutils")
        return 1
    print(f"✅ Se encontraron {len(printers)} impresora(s):")
    print()

    for i, printer in enumerate(printers, 1):
        print(f"Impresora #{i}:")
        print(f"  Ruta dispositivo:  {printer.device_path}")
        print(f"  Nombre:           {printer.friendly_name}")
        if printer.vendor_id:
            print(f"  Vendor ID:        {printer.vendor_id}")
        if printer.product_id:
            print(f"  Product ID:       {printer.product_id}")
        if printer.manufacturer:
            print(f"  Fabricante:       {printer.manufacturer}")
        if printer.product:
            print(f"  Producto:         {printer.product}")
        if printer.serial:
            print(f"  Serie:            {printer.serial}")
        is_thermal = detector.is_thermal_printer(printer)
        print(f"  Tipo:             {'🔥 Térmica' if is_thermal else '🖨️  Estándar'}")
        print(f"  Probando conexión...", end=' ')
        if detector.test_printer_connection(printer.device_path):
            print("✅ OK")
        else:
            print("❌ FALLÓ")
            print(f"    Sugerencia: sudo chmod 666 {printer.device_path}")
        print()

    print("=" * 70)
    print("Recomendación:")

    if printers:
        primary = printers[0]
        print(f"  Usar: {primary.device_path}")
        print(f"  Nombre: {primary.friendly_name}")
    print("=" * 70)

    return 0

if __name__ == '__main__':
    sys.exit(main())