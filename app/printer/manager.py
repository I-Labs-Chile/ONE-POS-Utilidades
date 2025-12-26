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
        from app.printer.windows_spooler import WindowsEscposSender
        printer_name = os.environ.get("PRINTER_NAME") or os.environ.get("WINDOWS_PRINTER_NAME") or "POS-58"
        return WindowsEscposSender(printer_name)
    else:
        # Linux y otros: mantener backend actual sin cambios
        from app.utils.escpos import EscposSender
        return EscposSender(interface=interface, host=host, port=port, usb_vendor=usb_vendor, usb_product=usb_product)