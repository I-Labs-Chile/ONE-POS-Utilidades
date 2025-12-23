# -*- coding: utf-8 -*-
# Lógica de prueba de impresora
# Envía un ticket de bienvenida y un código QR con la URL local

import os
import time
from typing import Dict

from app.core.worker import PrintWorker
from app.utils.escpos import EscposSender
from app.utils.network import get_primary_ip


def _build_selftest_url() -> str:
    # Construye la URL pública del servidor usando la IP local y el puerto
    ip = get_primary_ip()
    try:
        port = int(os.environ.get("SERVER_PORT", "8080"))
    except Exception:
        port = 8080
    return f"http://{ip}:{port}/"


def run_printer_selftest(worker: PrintWorker) -> Dict[str, object]:
    # Ejecuta una impresión de prueba para validar conexión con la impresora
    # Devuelve un diccionario con el resultado para exponerlo por la API
    resultado: Dict[str, object] = {
        "ok": False,
        "url": "",
        "detalle": "",
    }
    url = _build_selftest_url()
    resultado["url"] = url
    try:
        print("# Iniciando prueba de impresora")
        sender = EscposSender(
            interface=worker.printer_interface,
            host=worker.printer_host,
            port=worker.printer_port,
            usb_vendor=worker.usb_vendor,
            usb_product=worker.usb_product,
        )
        print("# Impresora conectada correctamente para prueba de conexión")
        sender.init()
        sender.text("Bienvenido a ONE-POS Utilidades")
        sender.text("Prueba de conexión de impresora")
        sender.text(time.strftime("Fecha y hora: %Y-%m-%d %H:%M:%S"))
        sender.feed(1)
        sender.text("Escanee este código QR para abrir la interfaz web:")
        sender.print_qr(url)
        sender.feed(2)
        sender.cut()
        sender.close()
        resultado["ok"] = True
        resultado["detalle"] = "Prueba de impresión enviada correctamente"
        print("# Prueba de impresión enviada correctamente")
    except Exception as e:
        resultado["detalle"] = str(e)
        print(f"# Error en prueba de impresora: {e}")
    return resultado
