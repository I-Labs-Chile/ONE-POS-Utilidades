# -*- coding: utf-8 -*-
# Selector de backend por SO: Windows → spooler RAW; Linux → backend actual
import os
import platform
from typing import Optional

def create_sender(interface: str, host: str, port: int, usb_vendor: int, usb_product: int):
    # Switch de desarrollo: permite forzar backend con PRINTER_BACKEND env var
    # Valores: "windows" o "linux"
    # Si no está definida, usa detección automática por plataforma
    forced_backend = os.environ.get("PRINTER_BACKEND", "").lower()
    
    if forced_backend == "windows":
        use_windows = True
    elif forced_backend == "linux":
        use_windows = False
    else:
        # Detección automática
        use_windows = platform.system() == "Windows"
    
    if use_windows:
        from onepos_common.windows_spooler import WindowsEscposSender, resolve_printer_name
        printer_name = resolve_printer_name()
        if not printer_name:
            raise RuntimeError("No se encontró ninguna impresora instalada en Windows (configura PRINTER_NAME en .env)")
        print(f"# Backend Windows: usando impresora '{printer_name}'")
        return WindowsEscposSender(printer_name)
    else:
        # Linux y otros: mantener backend actual sin cambios
        from onepos_common.escpos import EscposSender
        return EscposSender(interface=interface, host=host, port=port, usb_vendor=usb_vendor, usb_product=usb_product)